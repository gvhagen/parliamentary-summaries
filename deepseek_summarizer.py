import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import requests
import os
from dataclasses import dataclass

@dataclass
class ChunkInfo:
    """Information about a text chunk"""
    chunk_number: int
    start_pos: int
    end_pos: int
    text: str
    topics_mentioned: List[str] = None

class DeepSeekParliamentarySummarizer:
    """
    Summarizer for parliamentary debates using DeepSeek API
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the summarizer
        
        Args:
            api_key: DeepSeek API key (or set DEEPSEEK_API_KEY env var)
        """
        api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DeepSeek API key required. Set DEEPSEEK_API_KEY environment variable or pass api_key parameter")
        
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.max_chunk_size = 15000  # Further reduced for faster processing
        
        # Headers for API requests
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Connection": "keep-alive",  # Reuse connections
            "User-Agent": "Parliamentary-Summarizer/1.0"
        }
        
        # Create persistent session for connection reuse
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Configure session for better performance
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=1,
            pool_maxsize=1,
            max_retries=3
        )
        self.session.mount('https://', adapter)
    
    def make_api_request(self, messages: List[Dict], max_tokens: int = 2000, model: str = "deepseek-chat") -> str:
        """
        Make a request to DeepSeek API
        
        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens in response
            model: DeepSeek model to use
            
        Returns:
            Response text from the API
        """
        # Clean messages to avoid encoding issues
        cleaned_messages = []
        for message in messages:
            cleaned_content = message['content']
            # Replace problematic Unicode characters
            cleaned_content = cleaned_content.replace(''', "'").replace(''', "'")
            cleaned_content = cleaned_content.replace('"', '"').replace('"', '"')
            cleaned_content = cleaned_content.replace('–', '-').replace('—', '-')
            cleaned_content = cleaned_content.replace('…', '...')
            
            cleaned_messages.append({
                'role': message['role'],
                'content': cleaned_content
            })
        
        payload = {
            "model": model,
            "messages": cleaned_messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,  # Low temperature for consistent, factual responses
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            print(f"DeepSeek API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            raise
        except KeyError as e:
            print(f"Unexpected API response format: {e}")
            print(f"Response: {response.text if 'response' in locals() else 'No response'}")
            raise
    
    def clean_text_for_api(self, text: str) -> str:
        """
        Clean text to avoid Unicode encoding issues
        
        Args:
            text: Input text with potential Unicode issues
            
        Returns:
            Cleaned text safe for API transmission
        """
        if not text:
            return ""
        
        # Replace problematic Unicode characters
        replacements = {
            ''': "'", ''': "'",  # Smart quotes
            '"': '"', '"': '"',  # Smart double quotes
            '–': '-', '—': '-',  # Em/en dashes
            '…': '...',          # Ellipsis
            '€': 'EUR',          # Euro symbol
            '°': ' degrees',     # Degree symbol
            '\u2018': "'",       # Left single quotation mark
            '\u2019': "'",       # Right single quotation mark
            '\u201c': '"',       # Left double quotation mark
            '\u201d': '"',       # Right double quotation mark
            '\u2013': '-',       # En dash
            '\u2014': '-',       # Em dash
            '\u2026': '...',     # Horizontal ellipsis
        }
        
        cleaned_text = text
        for old, new in replacements.items():
            cleaned_text = cleaned_text.replace(old, new)
        
        # More aggressive cleaning: encode to ASCII and ignore errors
        try:
            # Try UTF-8 first
            cleaned_text.encode('utf-8')
        except UnicodeEncodeError:
            # If that fails, force ASCII
            cleaned_text = cleaned_text.encode('ascii', errors='ignore').decode('ascii')
        
        return cleaned_text

    def identify_speakers_and_parties(self, text: str) -> Dict[str, str]:
        """
        Extract speaker names and their party affiliations from the text
        
        Args:
            text: Parliamentary debate text
            
        Returns:
            Dictionary mapping speaker names to parties
        """
        messages = [
            {
                "role": "user",
                "content": f"""
Analyze this Dutch parliamentary debate text and extract all speakers and their party affiliations.

Look for patterns like:
- "De heer [Name] ([Party]):"
- "Mevrouw [Name] ([Party]):"
- "Minister [Name]:"
- etc.

Return ONLY a JSON object mapping speaker names to their parties/roles:
{{
    "speaker_name": "party_or_role",
    "another_speaker": "another_party"
}}

Text to analyze:
{text[:5000]}...
"""
            }
        ]
        
        try:
            response_text = self.make_api_request(messages, max_tokens=1000)
            
            # Try to parse the JSON response
            # Sometimes the response includes extra text, so extract JSON
            json_match = re.search(r'\{[^}]*\}', response_text, re.DOTALL)
            if json_match:
                speakers = json.loads(json_match.group())
                return speakers
            else:
                # Fallback: try to parse the entire response
                speakers = json.loads(response_text)
                return speakers
        except Exception as e:
            print(f"Error identifying speakers: {e}")
            return {}
    
    def chunk_text_smartly(self, text: str) -> List[ChunkInfo]:
        """
        Split text into chunks, trying to preserve logical sections
        
        Args:
            text: Full parliamentary debate text
            
        Returns:
            List of ChunkInfo objects
        """
        chunks = []
        
        # Try to split on natural boundaries (speakers, agenda items, etc.)
        # Look for common patterns in Dutch parliamentary texts
        split_patterns = [
            r'\n\n(?=De heer|Mevrouw|Minister)',  # New speaker
            r'\n\n(?=Agendapunt|AGENDAPUNT)',     # New agenda item
            r'\n\n(?=Voorzitter:)',               # Chairman
            r'\n\n(?=[A-Z][a-z]+ [A-Z][a-z]+:)', # General speaker pattern
        ]
        
        current_pos = 0
        chunk_num = 1
        
        while current_pos < len(text):
            # Determine chunk end position
            target_end = min(current_pos + self.max_chunk_size, len(text))
            
            # If this would be the last chunk or we're near the end, take everything
            if target_end >= len(text) - 1000:
                chunk_end = len(text)
            else:
                # Try to find a good break point
                chunk_end = target_end
                best_break = None
                
                # Look for natural breaks within the last 2000 chars of the chunk
                search_start = max(target_end - 2000, current_pos)
                search_text = text[search_start:target_end + 1000]  # Look a bit ahead too
                
                for pattern in split_patterns:
                    matches = list(re.finditer(pattern, search_text))
                    if matches:
                        # Take the match closest to our target
                        for match in matches:
                            abs_pos = search_start + match.start()
                            if current_pos + 5000 <= abs_pos <= target_end + 500:  # Reasonable range
                                if best_break is None or abs(abs_pos - target_end) < abs(best_break - target_end):
                                    best_break = abs_pos
                
                if best_break:
                    chunk_end = best_break
            
            # Extract chunk
            chunk_text = text[current_pos:chunk_end].strip()
            
            if chunk_text:  # Only add non-empty chunks
                chunk = ChunkInfo(
                    chunk_number=chunk_num,
                    start_pos=current_pos,
                    end_pos=chunk_end,
                    text=chunk_text
                )
                chunks.append(chunk)
                chunk_num += 1
            
            current_pos = chunk_end
        
        print(f"Split text into {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i+1}: {len(chunk.text)} characters")
        
        return chunks
    
    def extract_json_from_response(self, response_text: str) -> Dict:
        """
        Robustly extract JSON from API response that might have extra text
        """
        # Method 1: Try to parse the entire response
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass
        
        # Method 2: Find JSON between curly braces
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Method 3: Find JSON between triple backticks (markdown)
        code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Method 4: Try to fix common JSON issues
        try:
            # Fix trailing commas
            fixed_text = re.sub(r',(\s*[}\]])', r'\1', response_text)
            # Fix single quotes
            fixed_text = re.sub(r"'([^']*)':", r'"\1":', fixed_text)
            
            json_match = re.search(r'\{.*\}', fixed_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        # Method 5: Manual parsing for simple cases
        try:
            # Look for topics array specifically
            topics_match = re.search(r'"topics"\s*:\s*\[(.*?)\]', response_text, re.DOTALL)
            if topics_match:
                return {
                    "topics": [],
                    "decisions": [],
                    "extracted_from_partial": True
                }
        except:
            pass
        
        # If all fails, return error structure
        return {
            "error": "Could not parse JSON response",
            "raw_response": response_text[:500],
            "topics": [],
            "decisions": []
        }

    def summarize_chunk(self, chunk: ChunkInfo, speakers_map: Dict[str, str], 
                       meeting_info: Dict) -> Dict:
        """
        Summarize a single chunk with better JSON handling
        
        Args:
            chunk: ChunkInfo object with text to summarize
            speakers_map: Mapping of speakers to parties
            meeting_info: Information about the meeting
            
        Returns:
            Dictionary with chunk summary
        """
        # Use even shorter, more reliable prompt
        messages = [
            {
                "role": "user",
                "content": f"""
Extract topics and party positions from this Dutch parliament text. Respond with valid JSON only.

{{
    "topics": [
        {{
            "topic": "Topic name", 
            "party_positions": [{{"party": "Party", "position": "Position"}}]
        }}
    ],
    "decisions": ["Any decisions"]
}}

Text:
{chunk.text[:10000]}
"""
            }
        ]
        
        try:
            response_text = self.make_api_request(messages, max_tokens=800)  # Even smaller
            
            # Use robust JSON extraction
            chunk_analysis = self.extract_json_from_response(response_text)
            chunk_analysis['chunk_number'] = chunk.chunk_number
            
            # Ensure required fields exist
            if 'topics' not in chunk_analysis:
                chunk_analysis['topics'] = []
            if 'decisions' not in chunk_analysis:
                chunk_analysis['decisions'] = []
                
            return chunk_analysis
            
        except Exception as e:
            print(f"    Error in chunk {chunk.chunk_number}: {e}")
            return {
                'chunk_number': chunk.chunk_number,
                'error': str(e),
                'topics': [],
                'decisions': []
            }
    
    def combine_chunk_summaries(self, chunk_summaries: List[Dict], 
                               meeting_info: Dict) -> Dict:
        """
        Combine multiple chunk summaries into a comprehensive meeting summary
        
        Args:
            chunk_summaries: List of chunk analysis results
            meeting_info: Meeting metadata
            
        Returns:
            Complete meeting summary
        """
        # Collect all topics across chunks
        all_topics = {}
        all_decisions = []
        
        for chunk_summary in chunk_summaries:
            if 'topics' in chunk_summary:
                for topic_info in chunk_summary['topics']:
                    topic_name = topic_info.get('topic', 'Unknown Topic')
                    
                    if topic_name not in all_topics:
                        all_topics[topic_name] = {
                            'topic': topic_name,
                            'description': topic_info.get('description', f"Discussion about {topic_name}"),
                            'party_positions': [],
                            'mentioned_in_chunks': []
                        }
                    
                    # Add party positions
                    all_topics[topic_name]['party_positions'].extend(
                        topic_info.get('party_positions', [])
                    )
                    all_topics[topic_name]['mentioned_in_chunks'].append(
                        chunk_summary.get('chunk_number', 0)
                    )
            
            # Collect decisions
            all_decisions.extend(chunk_summary.get('decisions', []))
            all_decisions.extend(chunk_summary.get('key_decisions', []))  # Support both formats
        
        # Create final summary using DeepSeek
        topics_summary = []
        for topic_name, topic_data in all_topics.items():
            # Consolidate party positions
            party_positions_map = {}
            for pos in topic_data['party_positions']:
                party = pos.get('party', 'Unknown')
                position = pos.get('position', 'No position stated')
                if party in party_positions_map:
                    party_positions_map[party] += f"; {position}"
                else:
                    party_positions_map[party] = position
            
            topics_summary.append({
                'topic': topic_name,
                'party_positions': party_positions_map,
                'chunks': topic_data['mentioned_in_chunks']
            })
        
        # Create concise final summary prompt
        messages = [
            {
                "role": "user",
                "content": f"""
Create final summary for Dutch parliamentary meeting.

Meeting: {meeting_info.get('vergadering_titel', 'Unknown')}
Date: {meeting_info.get('vergadering_datum', 'Unknown')}

Topics found: {len(topics_summary)}
Decisions found: {len(all_decisions)}

Respond with JSON:
{{
    "executive_summary": "2-3 sentence overview",
    "main_topics": [
        {{
            "topic": "Topic name",
            "summary": "What was discussed",
            "party_positions": {{"Party": "Position"}},
            "outcome": "Result or next steps"
        }}
    ],
    "key_decisions": ["List of decisions"],
    "political_dynamics": "Brief analysis of agreements/disagreements"
}}

Keep it concise and factual.
"""
            }
        ]
        
        try:
            response_text = self.make_api_request(messages, max_tokens=1500)
            final_summary = self.extract_json_from_response(response_text)
            
            # Add metadata
            final_summary['meeting_info'] = meeting_info
            final_summary['processing_info'] = {
                'chunks_processed': len(chunk_summaries),
                'total_topics_found': len(all_topics),
                'processing_date': datetime.now().isoformat(),
                'ai_model': 'deepseek-chat'
            }
            
            # Ensure required fields exist
            if 'main_topics' not in final_summary:
                final_summary['main_topics'] = []
            if 'key_decisions' not in final_summary:
                final_summary['key_decisions'] = list(set(all_decisions))  # Remove duplicates
            if 'executive_summary' not in final_summary:
                final_summary['executive_summary'] = f"Parliamentary meeting covering {len(all_topics)} main topics with {len(all_decisions)} decisions made."
            
            return final_summary
            
        except Exception as e:
            print(f"Error creating final summary: {e}")
            # Return a basic summary with collected data
            return {
                'executive_summary': f"Parliamentary meeting on {meeting_info.get('vergadering_datum', 'unknown date')} covering {len(all_topics)} topics.",
                'main_topics': [
                    {
                        'topic': topic['topic'],
                        'summary': f"Discussion about {topic['topic']}",
                        'party_positions': topic['party_positions'],
                        'outcome': 'To be determined'
                    }
                    for topic in topics_summary[:10]  # Limit to top 10
                ],
                'key_decisions': list(set(all_decisions)),
                'political_dynamics': 'Analysis not available due to processing error',
                'meeting_info': meeting_info,
                'processing_info': {
                    'chunks_processed': len(chunk_summaries),
                    'total_topics_found': len(all_topics),
                    'processing_date': datetime.now().isoformat(),
                    'ai_model': 'deepseek-chat',
                    'error': str(e)
                }
            }
    
    def debug_unicode_issues(self, text: str, sample_size: int = 1000) -> None:
        """
        Debug function to identify problematic Unicode characters
        """
        sample = text[:sample_size]
        print(f"Debugging Unicode in text sample...")
        print(f"Sample length: {len(sample)} characters")
        
        # Find problematic characters
        problematic_chars = []
        for i, char in enumerate(sample):
            try:
                char.encode('ascii')
            except UnicodeEncodeError:
                problematic_chars.append((i, char, ord(char), hex(ord(char))))
        
        if problematic_chars:
            print(f"Found {len(problematic_chars)} problematic characters:")
            for i, char, code, hex_code in problematic_chars[:10]:  # Show first 10
                print(f"  Position {i}: '{char}' (U+{hex_code[2:].upper().zfill(4)}, {code})")
        else:
            print("No problematic ASCII characters found")
    
    def summarize_parliamentary_meeting(self, verslag_data: Dict) -> Dict:
        """
        Complete pipeline to summarize a parliamentary meeting
        
        Args:
            verslag_data: Dictionary with meeting data and text content
            
        Returns:
            Complete summary of the meeting
        """
        print(f"\n=== Summarizing Meeting with DeepSeek ===")
        print(f"Meeting: {verslag_data.get('vergadering_titel', 'Unknown')}")
        print(f"Date: {verslag_data.get('vergadering_datum', 'Unknown')}")
        
        # Get the readable text
        text = verslag_data.get('readable_text', '')
        if not text:
            return {'error': 'No readable text found in verslag data'}
        
        print(f"Text length: {len(text)} characters")
        
        # Debug Unicode issues
        self.debug_unicode_issues(text)
        
        # Extract meeting info
        meeting_info = {
            'vergadering_titel': verslag_data.get('vergadering_titel'),
            'vergadering_datum': verslag_data.get('vergadering_datum'),
            'verslag_id': verslag_data.get('id'),
            'status': verslag_data.get('status')
        }
        
        # Step 1: Identify speakers and parties
        print("Step 1: Identifying speakers and parties...")
        speakers_map = self.identify_speakers_and_parties(text)
        print(f"Found {len(speakers_map)} speakers/parties")
        
        # Step 2: Chunk the text
        print("Step 2: Chunking text...")
        chunks = self.chunk_text_smartly(text)
        
        # Step 3: Summarize each chunk
        print("Step 3: Summarizing chunks...")
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            print(f"  Processing chunk {i+1}/{len(chunks)}...")
            chunk_summary = self.summarize_chunk(chunk, speakers_map, meeting_info)
            chunk_summaries.append(chunk_summary)
        
        # Step 4: Combine into final summary
        print("Step 4: Creating final summary...")
        final_summary = self.combine_chunk_summaries(chunk_summaries, meeting_info)
        
        print("✓ Summary complete!")
        return final_summary

def main():
    """
    Main function to test the DeepSeek summarizer
    """
    print("=== DeepSeek Parliamentary Summarizer ===")
    
    # Check for API key
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ DEEPSEEK_API_KEY environment variable not set!")
        print("Please set your API key:")
        print("export DEEPSEEK_API_KEY='your-api-key-here'")
        print("\nGet your API key from: https://platform.deepseek.com/")
        return
    
    try:
        # Load parsed verslagen
        with open('verslagen_parsed.json', 'r', encoding='utf-8') as f:
            verslagen = json.load(f)
        
        # Find verslagen ready for summarization
        ready_verslagen = [v for v in verslagen if v.get('summary_ready', False)]
        
        if not ready_verslagen:
            print("No verslagen ready for summarization found!")
            print("Make sure you've run the document processor and XML parser first.")
            return
        
        print(f"Found {len(ready_verslagen)} verslagen ready for summarization")
        
        # Initialize summarizer
        summarizer = DeepSeekParliamentarySummarizer(api_key)
        
        # Process first verslag as test
        test_verslag = ready_verslagen[0]
        print(f"\nTesting with: {test_verslag.get('vergadering_titel', 'Unknown')}")
        
        # Create summary
        summary = summarizer.summarize_parliamentary_meeting(test_verslag)
        
        # Save result
        output_filename = f"deepseek_summary_{test_verslag.get('id', 'unknown')}.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ Summary saved to: {output_filename}")
        
        # Show preview
        if 'executive_summary' in summary:
            print(f"\nExecutive Summary:")
            print(f"  {summary['executive_summary']}")
            
            if 'main_topics' in summary:
                print(f"\nMain Topics ({len(summary['main_topics'])}):")
                for topic in summary['main_topics'][:3]:  # Show first 3
                    print(f"  - {topic.get('topic', 'Unknown topic')}")
        
        # Show cost estimate
        if 'processing_info' in summary:
            chunks = summary['processing_info'].get('chunks_processed', 0)
            estimated_tokens = chunks * 15000  # Rough estimate
            estimated_cost = (estimated_tokens / 1000000) * 0.14  # DeepSeek pricing
            print(f"\nEstimated cost: ~${estimated_cost:.3f} (vs ~${estimated_cost/0.14*0.25:.3f} with Claude Haiku)")
        
    except FileNotFoundError:
        print("verslagen_parsed.json not found. Please run the XML parser first.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()