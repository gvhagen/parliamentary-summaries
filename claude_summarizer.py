import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import anthropic
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

class ParliamentarySummarizer:
    """
    Summarizer for parliamentary debates using Claude API
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the summarizer
        
        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
        """
        api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_chunk_size = 50000  # Characters per chunk (roughly 12-15k tokens)
    
    def identify_speakers_and_parties(self, text: str) -> Dict[str, str]:
        """
        Extract speaker names and their party affiliations from the text
        
        Args:
            text: Parliamentary debate text
            
        Returns:
            Dictionary mapping speaker names to parties
        """
        prompt = f"""
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
        
        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Try to parse the JSON response
            import json
            speakers = json.loads(response.content[0].text)
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
    
    def summarize_chunk(self, chunk: ChunkInfo, speakers_map: Dict[str, str], 
                       meeting_info: Dict) -> Dict:
        """
        Summarize a single chunk of parliamentary debate
        
        Args:
            chunk: ChunkInfo object with text to summarize
            speakers_map: Mapping of speakers to parties
            meeting_info: Information about the meeting
            
        Returns:
            Dictionary with chunk summary
        """
        prompt = f"""
        You are analyzing a chunk from a Dutch parliamentary debate. Provide a structured analysis focusing on:
        1. Topics discussed in this chunk
        2. Party positions on those topics
        3. Key arguments made
        
        Meeting context:
        - Meeting: {meeting_info.get('vergadering_titel', 'Unknown')}
        - Date: {meeting_info.get('vergadering_datum', 'Unknown')}
        
        Known speakers and parties: {speakers_map}
        
        Please analyze this chunk and return a JSON object with this structure:
        {{
            "chunk_summary": "Brief overview of what was discussed in this chunk",
            "topics": [
                {{
                    "topic": "Main topic name (e.g., 'Corporate Taxation', 'Healthcare Budget')",
                    "description": "What specifically was discussed about this topic",
                    "party_positions": [
                        {{
                            "party": "Party name or speaker role",
                            "position": "Summary of their stance on this topic",
                            "key_quotes": ["Important quote if any"]
                        }}
                    ]
                }}
            ],
            "key_decisions": ["Any decisions, motions, or votes mentioned"],
            "notable_exchanges": ["Significant debates or disagreements"]
        }}
        
        Be objective and neutral. Focus on factual content, not rhetoric.
        
        Chunk text to analyze:
        {chunk.text}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON response
            chunk_analysis = json.loads(response.content[0].text)
            chunk_analysis['chunk_number'] = chunk.chunk_number
            return chunk_analysis
            
        except Exception as e:
            print(f"Error summarizing chunk {chunk.chunk_number}: {e}")
            return {
                'chunk_number': chunk.chunk_number,
                'error': str(e),
                'chunk_summary': 'Error processing this chunk'
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
        all_exchanges = []
        
        for chunk_summary in chunk_summaries:
            if 'topics' in chunk_summary:
                for topic_info in chunk_summary['topics']:
                    topic_name = topic_info['topic']
                    
                    if topic_name not in all_topics:
                        all_topics[topic_name] = {
                            'topic': topic_name,
                            'description': topic_info['description'],
                            'party_positions': [],
                            'mentioned_in_chunks': []
                        }
                    
                    # Add party positions
                    all_topics[topic_name]['party_positions'].extend(
                        topic_info.get('party_positions', [])
                    )
                    all_topics[topic_name]['mentioned_in_chunks'].append(
                        chunk_summary['chunk_number']
                    )
            
            # Collect decisions and exchanges
            all_decisions.extend(chunk_summary.get('key_decisions', []))
            all_exchanges.extend(chunk_summary.get('notable_exchanges', []))
        
        # Create final summary using Claude
        topics_json = json.dumps(list(all_topics.values()), ensure_ascii=False, indent=2)
        
        synthesis_prompt = f"""
        Create a comprehensive summary of this Dutch parliamentary meeting by synthesizing the analysis from multiple chunks.
        
        Meeting: {meeting_info.get('vergadering_titel', 'Unknown')}
        Date: {meeting_info.get('vergadering_datum', 'Unknown')}
        
        Topics and party positions found across chunks:
        {topics_json}
        
        Key decisions: {all_decisions}
        Notable exchanges: {all_exchanges}
        
        Please create a final summary with this structure:
        {{
            "executive_summary": "2-3 sentence overview of the entire meeting",
            "main_topics": [
                {{
                    "topic": "Topic name",
                    "summary": "What was discussed about this topic",
                    "party_positions": {{
                        "Party/Speaker": "Their overall position on this topic"
                    }},
                    "outcome": "Any decisions or next steps"
                }}
            ],
            "key_decisions": ["Final list of decisions/motions/votes"],
            "political_dynamics": "Brief analysis of agreements, disagreements, coalition dynamics",
            "next_steps": ["What happens next based on this meeting"]
        }}
        
        Be objective, factual, and politically neutral.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,
                messages=[{"role": "user", "content": synthesis_prompt}]
            )
            
            final_summary = json.loads(response.content[0].text)
            
            # Add metadata
            final_summary['meeting_info'] = meeting_info
            final_summary['processing_info'] = {
                'chunks_processed': len(chunk_summaries),
                'total_topics_found': len(all_topics),
                'processing_date': datetime.now().isoformat()
            }
            
            return final_summary
            
        except Exception as e:
            print(f"Error creating final summary: {e}")
            return {
                'error': str(e),
                'meeting_info': meeting_info,
                'raw_chunk_summaries': chunk_summaries
            }
    
    def summarize_parliamentary_meeting(self, verslag_data: Dict) -> Dict:
        """
        Complete pipeline to summarize a parliamentary meeting
        
        Args:
            verslag_data: Dictionary with meeting data and text content
            
        Returns:
            Complete summary of the meeting
        """
        print(f"\n=== Summarizing Meeting ===")
        print(f"Meeting: {verslag_data.get('vergadering_titel', 'Unknown')}")
        print(f"Date: {verslag_data.get('vergadering_datum', 'Unknown')}")
        
        # Get the readable text
        text = verslag_data.get('readable_text', '')
        if not text:
            return {'error': 'No readable text found in verslag data'}
        
        print(f"Text length: {len(text)} characters")
        
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
    Main function to test the summarizer
    """
    print("=== Parliamentary Summarizer ===")
    
    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set!")
        print("Please set your API key:")
        print("export ANTHROPIC_API_KEY='your-api-key-here'")
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
        summarizer = ParliamentarySummarizer(api_key)
        
        # Process first verslag as test
        test_verslag = ready_verslagen[0]
        print(f"\nTesting with: {test_verslag.get('vergadering_titel', 'Unknown')}")
        
        # Create summary
        summary = summarizer.summarize_parliamentary_meeting(test_verslag)
        
        # Save result
        output_filename = f"summary_{test_verslag.get('id', 'unknown')}.json"
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
        
    except FileNotFoundError:
        print("verslagen_parsed.json not found. Please run the XML parser first.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
