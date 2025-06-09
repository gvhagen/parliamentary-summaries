import tkapi
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import tempfile
import os
import time
from tqdm import tqdm  # For progress bar - install with: pip install tqdm

# For text extraction
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import mammoth
    MAMMOTH_AVAILABLE = True
except ImportError:
    MAMMOTH_AVAILABLE = False

class DocumentProcessor:
    """
    Enhanced processor to download and extract text from Tweede Kamer documents
    """
    
    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the processor with configurable rate limiting
        
        Args:
            rate_limit_delay: Seconds to wait between API requests (default: 1.0)
        """
        self.api = tkapi.TKApi()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TK-Summary-Bot/1.0'
        })
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    def explore_verslag_structure(self, verslag_id: str):
        """Explore the structure of a verslag to understand how to access documents"""
        try:
            self._rate_limit()
            
            # Get all verslagen and find the one we want
            verslagen = self.api.get_verslagen(max_items=100)
            verslag = None
            
            for v in verslagen:
                if v.id == verslag_id:
                    verslag = v
                    break
            
            if not verslag:
                print(f"Could not find verslag with ID {verslag_id}")
                return None
            
            print(f"Exploring verslag structure:")
            print(f"  - ID: {verslag.id}")
            print(f"  - Available attributes: {[attr for attr in dir(verslag) if not attr.startswith('_')]}")
            
            # Try different ways to access document content
            methods_to_try = [
                'get_resource_url_or_none',
                'url',
                'resource_url'
            ]
            
            for method in methods_to_try:
                if hasattr(verslag, method):
                    try:
                        result = getattr(verslag, method)
                        if callable(result):
                            result = result()
                        print(f"  - {method}: {result}")
                    except Exception as e:
                        print(f"  - {method}: Error - {e}")
            
            # Try to get related documents
            if hasattr(verslag, 'related_items'):
                try:
                    documents = verslag.related_items('Document')
                    print(f"  - Related documents: {len(documents) if documents else 0}")
                    if documents:
                        doc = documents[0]
                        print(f"    - Document attributes: {[attr for attr in dir(doc) if not attr.startswith('_')]}")
                        if hasattr(doc, 'get_resource_url_or_none'):
                            print(f"    - Document URL: {doc.get_resource_url_or_none()}")
                except Exception as e:
                    print(f"  - Related documents error: {e}")
            
            return verslag
            
        except Exception as e:
            print(f"Error exploring verslag structure: {e}")
            return None

    def get_document_content(self, verslag_id: str, retry_count: int = 3) -> Optional[bytes]:
        """
        Download the raw document content for a verslag with retry logic
        
        Args:
            verslag_id: ID of the verslag
            retry_count: Number of retries on failure
            
        Returns:
            Raw document bytes or None
        """
        for attempt in range(retry_count):
            try:
                self._rate_limit()
                
                # First, let's explore the structure (only on first attempt)
                if attempt == 0:
                    verslag = self.explore_verslag_structure(verslag_id)
                    if not verslag:
                        return None
                
                # Try different ways to get the document URL
                document_url = None
                
                # Method 1: Direct resource URL
                if hasattr(verslag, 'get_resource_url_or_none'):
                    try:
                        document_url = verslag.get_resource_url_or_none()
                        if attempt == 0:
                            print(f"Method 1 - Direct resource URL: {document_url}")
                    except Exception as e:
                        if attempt == 0:
                            print(f"Method 1 failed: {e}")
                
                # Method 2: Through URL property
                if not document_url and hasattr(verslag, 'url'):
                    try:
                        base_url = verslag.url
                        if base_url:
                            # Try appending /resource to the base URL
                            document_url = base_url + '/resource'
                            if attempt == 0:
                                print(f"Method 2 - URL + /resource: {document_url}")
                    except Exception as e:
                        if attempt == 0:
                            print(f"Method 2 failed: {e}")
                
                # Method 3: Through related documents
                if not document_url and hasattr(verslag, 'related_items'):
                    try:
                        documents = verslag.related_items('Document')
                        if documents:
                            document = documents[0]
                            if hasattr(document, 'get_resource_url_or_none'):
                                document_url = document.get_resource_url_or_none()
                                if attempt == 0:
                                    print(f"Method 3 - Related document URL: {document_url}")
                    except Exception as e:
                        if attempt == 0:
                            print(f"Method 3 failed: {e}")
                
                # Method 4: Try direct API URL construction
                if not document_url:
                    # Construct URL based on tkapi patterns
                    base_api_url = "https://opendata.tweedekamer.nl/v4/2.0"
                    document_url = f"{base_api_url}/Verslag('{verslag_id}')/resource"
                    if attempt == 0:
                        print(f"Method 4 - Direct API construction: {document_url}")
                
                if document_url:
                    if attempt == 0:
                        print(f"Attempting to download from: {document_url}")
                    
                    self._rate_limit()
                    response = self.session.get(document_url, timeout=30)
                    
                    if response.status_code == 200:
                        print(f"Successfully downloaded {len(response.content)} bytes")
                        return response.content
                    elif response.status_code == 429:  # Too Many Requests
                        wait_time = (attempt + 1) * 5  # Exponential backoff
                        print(f"Rate limited. Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Download failed with status code: {response.status_code}")
                        if attempt == 0:
                            print(f"Response: {response.text[:200]}")
                        return None
                else:
                    print(f"No document URL found for verslag {verslag_id}")
                    return None
                    
            except requests.exceptions.Timeout:
                print(f"Timeout on attempt {attempt + 1}/{retry_count}")
                if attempt < retry_count - 1:
                    time.sleep(5)
                    continue
            except Exception as e:
                print(f"Error downloading document for {verslag_id}: {e}")
                if attempt == 0:
                    import traceback
                    traceback.print_exc()
                if attempt < retry_count - 1:
                    time.sleep(5)
                    continue
        
        return None
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> Optional[str]:
        """Extract text from PDF content"""
        if not PDF_AVAILABLE:
            print("PyPDF2 not available. Install with: pip install PyPDF2")
            return None
        
        try:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(pdf_content)
                temp_file.flush()
                
                with open(temp_file.name, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    
                    return text.strip()
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return None
    
    def extract_text_from_docx(self, docx_content: bytes) -> Optional[str]:
        """Extract text from DOCX content"""
        if not DOCX_AVAILABLE:
            print("python-docx not available. Install with: pip install python-docx")
            return None
        
        try:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(docx_content)
                temp_file.flush()
                
                doc = DocxDocument(temp_file.name)
                text = ""
                
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                
                return text.strip()
        except Exception as e:
            print(f"Error extracting DOCX text: {e}")
            return None
    
    def extract_text_from_doc(self, doc_content: bytes) -> Optional[str]:
        """Extract text from DOC content using mammoth"""
        if not MAMMOTH_AVAILABLE:
            print("mammoth not available. Install with: pip install mammoth")
            return None
        
        try:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(doc_content)
                temp_file.flush()
                
                with open(temp_file.name, 'rb') as file:
                    result = mammoth.extract_raw_text(file)
                    return result.value.strip()
        except Exception as e:
            print(f"Error extracting DOC text: {e}")
            return None
    
    def detect_content_type(self, content: bytes) -> str:
        """Detect the content type of the document"""
        if content.startswith(b'%PDF'):
            return 'pdf'
        elif content.startswith(b'PK'):  # ZIP-based formats like DOCX
            return 'docx'
        elif content.startswith(b'\xd0\xcf\x11\xe0'):  # OLE format like DOC
            return 'doc'
        elif content.startswith(b'<?xml') or content.startswith(b'\xef\xbb\xbf<?xml'):  # XML with or without BOM
            return 'xml'
        else:
            return 'unknown'
    
    def extract_text_from_xml(self, xml_content: bytes) -> Optional[str]:
        """Extract text from XML content (Tweede Kamer vergaderverslag format)"""
        try:
            import xml.etree.ElementTree as ET
            
            # Remove BOM if present
            if xml_content.startswith(b'\xef\xbb\xbf'):
                xml_content = xml_content[3:]
            
            # Parse XML
            root = ET.fromstring(xml_content.decode('utf-8'))
            
            # Extract all text content from XML
            text_parts = []
            
            def extract_text_recursive(element):
                # Add element text
                if element.text and element.text.strip():
                    text_parts.append(element.text.strip())
                
                # Process all child elements
                for child in element:
                    extract_text_recursive(child)
                    # Add tail text (text after child element)
                    if child.tail and child.tail.strip():
                        text_parts.append(child.tail.strip())
            
            extract_text_recursive(root)
            
            # Join all text parts with newlines
            return '\n'.join(text_parts)
            
        except Exception as e:
            print(f"Error extracting XML text: {e}")
            # Fallback: try to extract text using regex
            try:
                import re
                # Remove XML tags
                text = xml_content.decode('utf-8', errors='ignore')
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text)
                return text.strip()
            except:
                return None
    
    def extract_text_from_document(self, document_content: bytes) -> Optional[str]:
        """
        Extract text from document based on its type
        
        Args:
            document_content: Raw document bytes
            
        Returns:
            Extracted text or None
        """
        content_type = self.detect_content_type(document_content)
        
        print(f"Detected content type: {content_type}")
        
        if content_type == 'pdf':
            return self.extract_text_from_pdf(document_content)
        elif content_type == 'docx':
            return self.extract_text_from_docx(document_content)
        elif content_type == 'doc':
            return self.extract_text_from_doc(document_content)
        elif content_type == 'xml':
            return self.extract_text_from_xml(document_content)
        else:
            print(f"Unsupported content type: {content_type}")
            # Try to decode as plain text as fallback
            try:
                return document_content.decode('utf-8', errors='ignore')
            except:
                return None
    
    def process_verslag_with_content(self, verslag_data: Dict, verbose: bool = True) -> Dict:
        """
        Process a verslag and extract its text content
        
        Args:
            verslag_data: Dictionary with verslag information
            verbose: Whether to print detailed output
            
        Returns:
            Enhanced dictionary with text content
        """
        if verbose:
            print(f"\nProcessing verslag: {verslag_data.get('vergadering_titel', 'Unknown')}")
            print(f"Verslag ID: {verslag_data['id']}")
        
        # Download document content
        document_content = self.get_document_content(verslag_data['id'])
        
        if document_content:
            if verbose:
                print(f"Downloaded document: {len(document_content)} bytes")
            
            # Extract text
            extracted_text = self.extract_text_from_document(document_content)
            
            if extracted_text:
                if verbose:
                    print(f"Extracted text: {len(extracted_text)} characters")
                verslag_data['document_text'] = extracted_text
                verslag_data['document_size_bytes'] = len(document_content)
                verslag_data['text_length'] = len(extracted_text)
                verslag_data['content_extracted'] = True
                
                # Preview of the text
                if verbose:
                    preview = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
                    print(f"Text preview: {preview}")
            else:
                print("Failed to extract text from document")
                verslag_data['content_extracted'] = False
                verslag_data['error'] = "Text extraction failed"
        else:
            print("Failed to download document")
            verslag_data['content_extracted'] = False
            verslag_data['error'] = "Document download failed"
        
        return verslag_data

def save_to_json(data: List[Dict], filename: str):
    """Save data to JSON with proper encoding"""
    def convert_enums(item):
        if isinstance(item, dict):
            return {k: convert_enums(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [convert_enums(v) for v in item]
        elif hasattr(item, '__str__') and not isinstance(item, (str, int, float, bool)) and item is not None:
            return str(item)
        else:
            return item
    
    converted_data = convert_enums(data)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(data)} items to {filename}")

def save_checkpoint(processed_verslagen: List[Dict], checkpoint_file: str = "processing_checkpoint.json"):
    """Save processing checkpoint to resume later if needed"""
    checkpoint_data = {
        "timestamp": datetime.now().isoformat(),
        "processed_count": len(processed_verslagen),
        "processed_ids": [v['id'] for v in processed_verslagen],
        "data": processed_verslagen
    }
    save_to_json(checkpoint_data, checkpoint_file)

def load_checkpoint(checkpoint_file: str = "processing_checkpoint.json") -> Optional[Dict]:
    """Load processing checkpoint if it exists"""
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
    return None

def main():
    """
    Main function to process documents and extract text
    """
    print("=== Tweede Kamer Document Processor ===")
    print()
    
    # Check what text extraction libraries are available
    print("Available text extraction libraries:")
    print(f"  - PyPDF2 (PDF): {'✓' if PDF_AVAILABLE else '✗ (install with: pip install PyPDF2)'}")
    print(f"  - python-docx (DOCX): {'✓' if DOCX_AVAILABLE else '✗ (install with: pip install python-docx)'}")
    print(f"  - mammoth (DOC): {'✓' if MAMMOTH_AVAILABLE else '✗ (install with: pip install mammoth)'}")
    print()
    
    # Configuration
    RATE_LIMIT_DELAY = 1.0  # Seconds between requests
    SAVE_CHECKPOINT_EVERY = 10  # Save progress every N documents
    RESUME_FROM_CHECKPOINT = True  # Whether to resume from checkpoint if available
    
    # Load existing plenaire verslagen
    try:
        with open('plenaire_verslagen.json', 'r', encoding='utf-8') as f:
            plenaire_verslagen = json.load(f)
        
        print(f"Found {len(plenaire_verslagen)} plenaire verslagen to process")
        
        # Check for existing checkpoint
        processed_verslagen = []
        processed_ids = set()
        start_index = 0
        
        if RESUME_FROM_CHECKPOINT:
            checkpoint = load_checkpoint()
            if checkpoint:
                print(f"\nFound checkpoint from {checkpoint['timestamp']}")
                print(f"Already processed: {checkpoint['processed_count']} documents")
                
                resume = input("Resume from checkpoint? (y/n): ").lower() == 'y'
                if resume:
                    processed_verslagen = checkpoint['data']
                    processed_ids = set(checkpoint['processed_ids'])
                    # Find where to start
                    for i, v in enumerate(plenaire_verslagen):
                        if v['id'] not in processed_ids:
                            start_index = i
                            break
        
        processor = DocumentProcessor(rate_limit_delay=RATE_LIMIT_DELAY)
        
        # Process all verslagen
        total_to_process = len(plenaire_verslagen) - start_index
        print(f"\nProcessing {total_to_process} documents...")
        print(f"Rate limit: {RATE_LIMIT_DELAY} seconds between requests")
        print(f"Estimated time: {total_to_process * (RATE_LIMIT_DELAY + 5) / 60:.1f} minutes\n")
        
        try:
            # Use tqdm for progress bar if available
            try:
                from tqdm import tqdm
                iterator = tqdm(enumerate(plenaire_verslagen[start_index:]), 
                              total=total_to_process,
                              desc="Processing verslagen")
            except ImportError:
                print("Install tqdm for progress bar: pip install tqdm")
                iterator = enumerate(plenaire_verslagen[start_index:])
            
            for i, verslag in iterator:
                actual_index = i + start_index
                
                # Skip if already processed
                if verslag['id'] in processed_ids:
                    continue
                
                print(f"\n--- Processing {actual_index + 1}/{len(plenaire_verslagen)} ---")
                
                try:
                    processed_verslag = processor.process_verslag_with_content(
                        verslag.copy(), 
                        verbose=(i < 3)  # Only verbose for first few
                    )
                    processed_verslagen.append(processed_verslag)
                    processed_ids.add(verslag['id'])
                    
                    # Save checkpoint periodically
                    if (i + 1) % SAVE_CHECKPOINT_EVERY == 0:
                        save_checkpoint(processed_verslagen)
                        print(f"Checkpoint saved ({len(processed_verslagen)} documents)")
                
                except KeyboardInterrupt:
                    print("\n\nProcessing interrupted by user")
                    save_checkpoint(processed_verslagen)
                    print(f"Progress saved. Processed {len(processed_verslagen)} documents.")
                    break
                except Exception as e:
                    print(f"Error processing verslag {verslag['id']}: {e}")
                    # Continue with next document
                    continue
        
        except Exception as e:
            print(f"Fatal error: {e}")
            save_checkpoint(processed_verslagen)
        
        # Save final results
        save_to_json(processed_verslagen, "verslagen_with_content.json")
        
        # Clean up checkpoint if we completed everything
        if len(processed_verslagen) == len(plenaire_verslagen):
            if os.path.exists("processing_checkpoint.json"):
                os.remove("processing_checkpoint.json")
                print("Removed checkpoint file (processing complete)")
        
        # Show summary
        successful = sum(1 for v in processed_verslagen if v.get('content_extracted', False))
        print(f"\n=== Processing Complete ===")
        print(f"Total documents: {len(plenaire_verslagen)}")
        print(f"Processed: {len(processed_verslagen)}")
        print(f"Successfully extracted text: {successful}")
        print(f"Failed: {len(processed_verslagen) - successful}")
        
        if successful > 0:
            print("\nReady for next step: AI summarization!")
            print("You now have text content that can be fed to an LLM for summarization.")
            
            # Calculate total text size
            total_chars = sum(v.get('text_length', 0) for v in processed_verslagen if v.get('content_extracted', False))
            print(f"Total text extracted: {total_chars:,} characters ({total_chars/1_000_000:.1f} million)")
        
    except FileNotFoundError:
        print("No plenaire_verslagen.json found. Please run tk_data_retriever.py first.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()