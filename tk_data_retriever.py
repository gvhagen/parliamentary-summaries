import tkapi
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from pathlib import Path

class TweedeKamerDataRetriever:
    """
    A class to retrieve and process Tweede Kamer data using the tkapi library
    """
    
    def __init__(self):
        self.api = tkapi.TKApi()
        self.session = requests.Session()
        
    def get_recent_plenaire_verslagen(self, days_back: int = 30, max_items: int = 50) -> List[Dict]:
        """
        Retrieve recent plenaire verslagen (plenary meeting reports)
        
        Args:
            days_back: Number of days to look back from today
            max_items: Maximum number of verslagen to retrieve
            
        Returns:
            List of verslagen data in a clean format
        """
        print(f"Fetching plenaire verslagen from the last {days_back} days...")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        try:
            # Get verslagen with date filter
            verslagen = self.api.get_verslagen(
                date_from=start_date.date(),
                date_to=end_date.date(),
                max_items=max_items
            )
            
            # Filter for plenaire vergaderingen and process the data
            plenaire_verslagen = []
            
            for verslag in verslagen:
                # Check if this is a plenary meeting (you might need to adjust this filter)
                vergadering = verslag.vergadering if hasattr(verslag, 'vergadering') else None
                
                if vergadering and hasattr(vergadering, 'soort') and 'plenair' in str(vergadering.soort).lower():
                    verslag_data = {
                        'id': verslag.id,
                        'titel': verslag.titel if hasattr(verslag, 'titel') else None,
                        'datum': verslag.datum.isoformat() if hasattr(verslag, 'datum') and verslag.datum else None,
                        'vergadering_id': vergadering.id if vergadering else None,
                        'vergadering_titel': vergadering.titel if vergadering and hasattr(vergadering, 'titel') else None,
                        'status': verslag.status if hasattr(verslag, 'status') else None,
                        'document_url': verslag.document_url if hasattr(verslag, 'document_url') else None,
                        'retrieved_at': datetime.now().isoformat()
                    }
                    plenaire_verslagen.append(verslag_data)
            
            print(f"Found {len(plenaire_verslagen)} plenaire verslagen")
            return plenaire_verslagen
            
        except Exception as e:
            print(f"Error fetching verslagen: {e}")
            return []
    
    def get_all_recent_verslagen(self, days_back: int = 30, max_items: int = 100) -> List[Dict]:
        """
        Get all recent verslagen (not just plenaire) for broader analysis
        
        Args:
            days_back: Number of days to look back
            max_items: Maximum number of items to retrieve
            
        Returns:
            List of all verslagen data
        """
        print(f"Fetching all verslagen from the last {days_back} days...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        try:
            verslagen = self.api.get_verslagen(
                date_from=start_date.date(),
                date_to=end_date.date(),
                max_items=max_items
            )
            
            processed_verslagen = []
            
            for verslag in verslagen:
                vergadering = verslag.vergadering if hasattr(verslag, 'vergadering') else None
                
                verslag_data = {
                    'id': verslag.id,
                    'titel': verslag.titel if hasattr(verslag, 'titel') else None,
                    'datum': verslag.datum.isoformat() if hasattr(verslag, 'datum') and verslag.datum else None,
                    'vergadering_id': vergadering.id if vergadering else None,
                    'vergadering_titel': vergadering.titel if vergadering and hasattr(vergadering, 'titel') else None,
                    'vergadering_soort': str(vergadering.soort) if vergadering and hasattr(vergadering, 'soort') else None,
                    'status': verslag.status if hasattr(verslag, 'status') else None,
                    'document_url': verslag.document_url if hasattr(verslag, 'document_url') else None,
                    'retrieved_at': datetime.now().isoformat()
                }
                processed_verslagen.append(verslag_data)
            
            print(f"Found {len(processed_verslagen)} total verslagen")
            return processed_verslagen
            
        except Exception as e:
            print(f"Error fetching verslagen: {e}")
            return []
    
    def download_verslag_document(self, verslag_data: Dict, download_dir: str = "documents") -> Optional[str]:
        """
        Download the actual document file for a verslag
        
        Args:
            verslag_data: Dictionary containing verslag information
            download_dir: Directory to save documents
            
        Returns:
            Path to downloaded file, or None if failed
        """
        if not verslag_data.get('document_url'):
            print(f"No document URL for verslag {verslag_data.get('id')}")
            return None
        
        # Create download directory
        Path(download_dir).mkdir(exist_ok=True)
        
        try:
            response = self.session.get(verslag_data['document_url'])
            response.raise_for_status()
            
            # Determine file extension from content type or URL
            content_type = response.headers.get('content-type', '')
            if 'pdf' in content_type:
                ext = '.pdf'
            elif 'word' in content_type or 'msword' in content_type:
                ext = '.doc'
            elif 'wordprocessingml' in content_type:
                ext = '.docx'
            else:
                ext = '.txt'  # fallback
            
            # Create filename
            filename = f"{verslag_data['id']}{ext}"
            filepath = Path(download_dir) / filename
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"Downloaded: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"Error downloading document for {verslag_data.get('id')}: {e}")
            return None
    
    def get_vergaderingen_info(self, days_back: int = 30) -> List[Dict]:
        """
        Get information about recent vergaderingen (meetings)
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of meeting information
        """
        print(f"Fetching vergaderingen from the last {days_back} days...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        try:
            vergaderingen = self.api.get_vergaderingen(
                date_from=start_date.date(),
                date_to=end_date.date(),
                max_items=100
            )
            
            vergaderingen_data = []
            
            for vergadering in vergaderingen:
                vergadering_data = {
                    'id': vergadering.id,
                    'titel': vergadering.titel if hasattr(vergadering, 'titel') else None,
                    'datum': vergadering.datum.isoformat() if hasattr(vergadering, 'datum') and vergadering.datum else None,
                    'soort': str(vergadering.soort) if hasattr(vergadering, 'soort') else None,
                    'aanvangstijd': str(vergadering.aanvangstijd) if hasattr(vergadering, 'aanvangstijd') else None,
                    'eindtijd': str(vergadering.eindtijd) if hasattr(vergadering, 'eindtijd') else None,
                    'retrieved_at': datetime.now().isoformat()
                }
                vergaderingen_data.append(vergadering_data)
            
            print(f"Found {len(vergaderingen_data)} vergaderingen")
            return vergaderingen_data
            
        except Exception as e:
            print(f"Error fetching vergaderingen: {e}")
            return []

def safe_serialize(obj):
    """
    Safely serialize objects that might contain enums or other non-JSON types
    """
    if hasattr(obj, '__str__'):
        return str(obj)
    return obj

def save_to_json(data: List[Dict], filename: str):
    """
    Save data to a JSON file with proper formatting
    
    Args:
        data: List of dictionaries to save
        filename: Output filename
    """
    # Convert any enum objects to strings
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

def explore_api():
    """
    Explore what methods are available in the tkapi
    """
    api = tkapi.TKApi()
    print("=== Exploring tkapi methods ===")
    
    # Print all available methods
    methods = [method for method in dir(api) if not method.startswith('_')]
    print("Available methods:")
    for method in methods:
        print(f"  - {method}")
    print()
    
    # Try to get some basic data to understand the structure
    try:
        print("1. Getting personen (people)...")
        personen = api.get_personen(max_items=5)
        print(f"Found {len(personen)} personen")
        if personen:
            persoon = personen[0]
            print(f"Sample persoon attributes: {[attr for attr in dir(persoon) if not attr.startswith('_')]}")
        print()
    except Exception as e:
        print(f"Error getting personen: {e}")
    
    # Try verslagen without date filters
    try:
        print("2. Getting verslagen (reports)...")
        verslagen = api.get_verslagen(max_items=5)
        print(f"Found {len(verslagen)} verslagen")
        if verslagen:
            verslag = verslagen[0]
            print(f"Sample verslag attributes: {[attr for attr in dir(verslag) if not attr.startswith('_')]}")
            print(f"Sample verslag data:")
            print(f"  ID: {getattr(verslag, 'id', 'N/A')}")
            print(f"  Titel: {getattr(verslag, 'titel', 'N/A')}")
            print(f"  Datum: {getattr(verslag, 'datum', 'N/A')}")
        print()
    except Exception as e:
        print(f"Error getting verslagen: {e}")
    
    # Try vergaderingen
    try:
        print("3. Getting vergaderingen (meetings)...")
        vergaderingen = api.get_vergaderingen(max_items=5)
        print(f"Found {len(vergaderingen)} vergaderingen")
        if vergaderingen:
            vergadering = vergaderingen[0]
            print(f"Sample vergadering attributes: {[attr for attr in dir(vergadering) if not attr.startswith('_')]}")
            print(f"Sample vergadering data:")
            print(f"  ID: {getattr(vergadering, 'id', 'N/A')}")
            print(f"  Titel: {getattr(vergadering, 'titel', 'N/A')}")
            print(f"  Datum: {getattr(vergadering, 'datum', 'N/A')}")
            print(f"  Soort: {getattr(vergadering, 'soort', 'N/A')}")
        print()
    except Exception as e:
        print(f"Error getting vergaderingen: {e}")

def main():
    """
    Main function to demonstrate the usage
    """
    # First explore the API to understand what's available
    explore_api()
    
    print("=== Tweede Kamer Data Retriever ===")
    print()
    
    # Get some basic data first
    try:
        api = tkapi.TKApi()
        
        print("1. Fetching recent verslagen...")
        verslagen = api.get_verslagen(max_items=20)
        print(f"Found {len(verslagen)} verslagen total")
        
        if verslagen:
            # Process the data
            processed_verslagen = []
            
            for verslag in verslagen:
                verslag_data = {
                    'id': getattr(verslag, 'id', None),
                    'titel': getattr(verslag, 'titel', None),
                    'datum': getattr(verslag, 'datum', None).isoformat() if hasattr(verslag, 'datum') and getattr(verslag, 'datum') else None,
                    'status': str(getattr(verslag, 'status', '')) if getattr(verslag, 'status', None) else None,
                    'soort': str(getattr(verslag, 'soort', '')) if getattr(verslag, 'soort', None) else None,
                    'retrieved_at': datetime.now().isoformat()
                }
                
                # Try to get vergadering info
                if hasattr(verslag, 'vergadering') and verslag.vergadering:
                    vergadering = verslag.vergadering
                    verslag_data['vergadering_id'] = getattr(vergadering, 'id', None)
                    verslag_data['vergadering_titel'] = getattr(vergadering, 'titel', None)
                    verslag_data['vergadering_soort'] = str(getattr(vergadering, 'soort', ''))
                    verslag_data['vergadering_datum'] = getattr(vergadering, 'datum', None).isoformat() if hasattr(vergadering, 'datum') and getattr(vergadering, 'datum') else None
                
                processed_verslagen.append(verslag_data)
            
            # Save all verslagen
            save_to_json(processed_verslagen, "recent_verslagen.json")
            
            # Filter for plenaire
            plenaire = [v for v in processed_verslagen if v.get('vergadering_soort') and 'plenair' in v['vergadering_soort'].lower()]
            if plenaire:
                save_to_json(plenaire, "plenaire_verslagen.json")
                print(f"Found {len(plenaire)} plenaire verslagen")
                print("Sample plenaire verslag:")
                print(json.dumps(plenaire[0], indent=2, ensure_ascii=False))
            else:
                print("No plenaire verslagen found in the recent data")
                print("Available vergadering types:")
                soorten = set(v.get('vergadering_soort', '') for v in processed_verslagen if v.get('vergadering_soort'))
                for soort in soorten:
                    print(f"  - {soort}")
        
        print("\n2. Fetching recent vergaderingen...")
        vergaderingen = api.get_vergaderingen(max_items=20)
        print(f"Found {len(vergaderingen)} vergaderingen")
        
        if vergaderingen:
            processed_vergaderingen = []
            
            for vergadering in vergaderingen:
                vergadering_data = {
                    'id': getattr(vergadering, 'id', None),
                    'titel': getattr(vergadering, 'titel', None),
                    'datum': getattr(vergadering, 'datum', None).isoformat() if hasattr(vergadering, 'datum') and getattr(vergadering, 'datum') else None,
                    'soort': str(getattr(vergadering, 'soort', '')),
                    'aanvangstijd': str(getattr(vergadering, 'aanvangstijd', '')) if hasattr(vergadering, 'aanvangstijd') else None,
                    'retrieved_at': datetime.now().isoformat()
                }
                processed_vergaderingen.append(vergadering_data)
            
            save_to_json(processed_vergaderingen, "recent_vergaderingen.json")
            print("Sample vergadering:")
            print(json.dumps(processed_vergaderingen[0], indent=2, ensure_ascii=False))
    
    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Basic Setup Complete! ===")
    print("You now have:")
    print("- recent_vergaderingen.json: List of recent meetings")
    print("- recent_verslagen.json: List of all recent meeting reports") 
    print("- plenaire_verslagen.json: List of plenary meeting reports (if any found)")
    print("\nNext step: We'll need to figure out filtering and document access!")

if __name__ == "__main__":
    # First install tkapi: pip install tkapi
    main()