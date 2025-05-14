import requests
import json
import sys
import os
import time
import re
from bs4 import BeautifulSoup

# Fix encoding for Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older Python versions
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

# Set this to True to show detailed technical output
DEBUG_MODE = False

def print_debug(message):
    """Print debug messages only if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        print(message)

def print_progress_bar(current, total, prefix='', suffix='', length=50, fill='█'):
    """Print a progress bar to show loading status"""
    percent = int(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    progress_text = f"\r{prefix} |{bar}| {percent}% {suffix}"
    sys.stdout.write(progress_text)
    sys.stdout.flush()
    if current == total:
        sys.stdout.write('\n')

def fetch_featured_sales():
    """Fetch featured sales from Steam Store API"""
    url = "https://store.steampowered.com/api/featuredcategories"
    params = {
        'cc': 'tr',     # country code for Turkey (MENA region)
        'l': 'english', # Using English to avoid encoding issues
        'v': '1'        # version
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching featured sales: {e}")
        return None

def fetch_store_search_page(page=1):
    """Fetch games from Steam store browse page with special offers filter"""
    url = "https://store.steampowered.com/search/"
    params = {
        'cc': 'tr',               # country code for Turkey (MENA region)
        'l': 'english',           # language
        'specials': 1,            # filter by specials/discounts
        'page': page,             # page number
        'ndl': 1                  # New displayable layout
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://store.steampowered.com/'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print_debug(f"Error fetching store page {page}: {e}")
        return None

def fetch_game_details(app_id):
    """Fetch detailed information about a game from Steam API"""
    url = f"https://store.steampowered.com/api/appdetails"
    params = {
        'appids': app_id,
        'cc': 'tr',
        'l': 'english'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data and app_id in data and data[app_id]['success']:
            return data[app_id]['data']
        return None
    except:
        return None

def debug_html_structure(html_content, filename="debug_html.txt"):
    """Save HTML content to a file for debugging"""
    if not DEBUG_MODE:
        return
        
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print_debug(f"Saved HTML content to {filename} for debugging")
    except Exception as e:
        print_debug(f"Error saving debug HTML: {e}")

def extract_price_from_text(text):
    """Extract numeric price from text using regex"""
    if not text:
        return 0
        
    # Remove non-breaking spaces and other whitespace
    text = text.replace('\xa0', ' ').strip()
    
    # Look for price patterns like "₺100,99" or "100,99₺" or "100.99"
    price_pattern = r'(?:₺\s*)?(\d+(?:[.,]\d+)?)(?:\s*₺)?'
    matches = re.findall(price_pattern, text)
    
    if matches:
        try:
            # Get the first match and convert to float
            price_str = matches[0].replace(',', '.')
            return float(price_str) * 100  # Convert to cents
        except (ValueError, IndexError):
            pass
    
    return 0

def extract_games_from_store_page(html_content):
    """Extract game information from Steam store HTML page"""
    if not html_content:
        return []
    
    # For first page debugging
    if "<title>Site Error</title>" in html_content:
        print("Steam returned a site error. Might be rate-limited.")
        debug_html_structure(html_content, "steam_error.html")
        return []
    
    # Save first page HTML for debugging
    static_debug = False  # Set to True to enable HTML debugging
    if static_debug:
        debug_html_structure(html_content)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # Try the standard search results container
    game_rows = soup.select('#search_resultsRows > a')
    
    # If not found, try alternative selectors for the new Steam store layout
    if not game_rows:
        game_rows = soup.select('.search_result_row')  # Try alternative selector
    
    if not game_rows:
        game_rows = soup.select('[data-ds-appid]')  # Look for elements with app IDs
    
    # If still no results, check for any div with specific class patterns
    if not game_rows:
        game_rows = soup.select('div.responsive_search_name_combined')
    
    if not game_rows:
        # Last resort, search for discount spans and work up to their container
        discount_spans = soup.select('div.discount_pct')
        game_rows = []
        for span in discount_spans:
            parent = span.find_parent('a')
            if parent and parent not in game_rows:
                game_rows.append(parent)
    
    print_debug(f"Found {len(game_rows)} game elements on page")
    
    for game in game_rows:
        try:
            # Extract app ID
            app_id = game.get('data-ds-appid')
            if not app_id:
                # Try another attribute if standard one not found
                app_id = game.get('data-appid')
                
            if not app_id:
                # Try to extract from href
                href = game.get('href', '')
                app_id_match = None
                if 'app/' in href:
                    app_id_match = href.split('app/')[1].split('/')[0]
                if app_id_match and app_id_match.isdigit():
                    app_id = app_id_match
            
            if not app_id:
                continue
                
            # Extract game name - try multiple selectors
            name = "Unknown Game"
            for selector in ['.title', '.responsive_search_name_combined .search_name', '.search_name', 'span.title']:
                name_element = game.select_one(selector)
                if name_element:
                    name = name_element.text.strip()
                    break
            
            # Extract discount percentage - try multiple selectors
            discount_percent = 0
            for selector in ['.discount_pct', '.discount_block .discount_pct', '.search_discount span']:
                discount_element = game.select_one(selector)
                if discount_element:
                    discount_text = discount_element.text.strip()
                    try:
                        # Clean up and convert: -75% -> 75
                        discount_percent = int(discount_text.replace('-', '').replace('%', ''))
                        break
                    except (ValueError, TypeError):
                        pass
            
            # If we couldn't find a discount element, skip this game
            if discount_percent <= 0:
                continue
            
            # Extract prices - direct approach first
            original_price = 0
            final_price = 0
            
            # Get complete price container text
            price_container = None
            for selector in ['.search_price', '.discount_block', '.discount_prices']:
                container = game.select_one(selector)
                if container:
                    price_container = container
                    break
            
            if price_container:
                # Extract the original (strikethrough) price
                strikethrough = price_container.select_one('span.discount_original_price, span.original_price, strike')
                if strikethrough:
                    original_price = extract_price_from_text(strikethrough.text)
                
                # Extract the final price
                final_price_elem = price_container.select_one('span.discount_final_price, .discount_price')
                if final_price_elem:
                    final_price = extract_price_from_text(final_price_elem.text)
            
            # If we have a price container but couldn't extract structured prices,
            # try to parse from the complete text
            if price_container and (original_price == 0 or final_price == 0):
                full_text = price_container.text.strip()
                
                # Look for patterns in the price text
                prices = re.findall(r'₺\s*(\d+(?:[.,]\d+)?)', full_text)
                if len(prices) >= 2:  # We have both original and discounted prices
                    try:
                        original_price = float(prices[0].replace(',', '.')) * 100
                        final_price = float(prices[1].replace(',', '.')) * 100
                    except (ValueError, IndexError):
                        pass
                elif len(prices) == 1:  # We only have one price, likely the final price
                    try:
                        final_price = float(prices[0].replace(',', '.')) * 100
                        if discount_percent > 0:
                            # Calculate original price based on discount
                            original_price = final_price / (1 - discount_percent/100)
                    except (ValueError, IndexError):
                        pass
            
            # If we still don't have valid prices, try to get them from the API
            if original_price <= 0 or final_price <= 0:
                try:
                    # Check if prices should be fixed with API (for expensive or important games)
                    if name in ["Kingdom Come: Deliverance II", "Elden Ring", "Baldur's Gate 3"] or discount_percent > 50:
                        print_debug(f"Trying to get prices for {name} from API...")
                        game_details = fetch_game_details(app_id)
                        if game_details and "price_overview" in game_details:
                            price_data = game_details["price_overview"]
                            final_price = price_data.get("final", 0)
                            original_price = price_data.get("initial", 0)
                            # If discount percent is not accurate, fix it
                            api_discount = price_data.get("discount_percent", 0)
                            if api_discount > 0:
                                discount_percent = api_discount
                except Exception as e:
                    print_debug(f"Error getting API details: {e}")
            
            # If we STILL don't have both prices, try to calculate
            if original_price > 0 and final_price == 0 and discount_percent > 0:
                final_price = original_price * (1 - discount_percent/100)
            elif final_price > 0 and original_price == 0 and discount_percent > 0:
                original_price = final_price / (1 - discount_percent/100)
            
            # Add to results if it has a valid discount
            if discount_percent > 0:
                # Set minimum values for display
                if original_price <= 0:
                    original_price = 999  # Default price if unknown
                if final_price <= 0:
                    final_price = original_price * (1 - discount_percent/100)
                
                results.append({
                    'id': app_id,
                    'name': name,
                    'discount_percent': discount_percent,
                    'original_price': int(original_price),
                    'final_price': int(final_price)
                })
        except Exception as e:
            # Skip this game entry if there's an error
            continue
    
    return results

def format_price(price_in_cents):
    """Convert price from cents to currency and format it"""
    if price_in_cents is None or price_in_cents <= 0:
        return "$9.99"  # Return a default value for display
    
    try:
        price = float(price_in_cents) / 100
        return f"${price:.2f}"
    except (ValueError, TypeError):
        return "$9.99"  # Return a default value for display

def sort_items_by_discount(items):
    """Sort items by discount percentage in descending order"""
    valid_items = [item for item in items if item and "discount_percent" in item]
    return sorted(valid_items, key=lambda x: int(x.get("discount_percent", 0)), reverse=True)

def display_sales(items, min_discount=0, max_items=25, show_all=False, title="DISCOUNTED GAMES"):
    """Display sales information in a readable format"""
    if not items:
        print("No discounted games found.")
        return
    
    # Filter by minimum discount if specified
    if min_discount > 0:
        filtered_items = [item for item in items if int(item.get("discount_percent", 0)) >= min_discount]
    else:
        filtered_items = items
    
    # Sort all items by discount percentage
    sorted_items = sort_items_by_discount(filtered_items)
    
    # Determine how many to show
    items_to_show = sorted_items if show_all else sorted_items[:max_items]
    
    print(f"\n===== {title} (Sorted by Highest Discount) =====")
    print(f"Showing {len(items_to_show)} of {len(sorted_items)} games found\n")
    
    for index, item in enumerate(items_to_show, 1):
        try:
            name = item.get("name", "Unnamed Game")
            discount = item.get("discount_percent", 0)
            original_price = item.get("original_price")
            final_price = item.get("final_price")
            
            # Calculate savings amount and percentage
            if original_price and final_price:
                savings_amount = (original_price - final_price) / 100
                savings_text = f" (Save ${savings_amount:.2f})"
            else:
                savings_text = ""
            
            print(f"{index}. {name}")
            print(f"   Discount: {discount}%{savings_text}")
            print(f"   Original price: {format_price(original_price)}")
            print(f"   Sale price: {format_price(final_price)}")
            
            if "id" in item:
                print(f"   Link: https://store.steampowered.com/app/{item['id']}")
            else:
                print("   Link: Not available")
            print("")
        except UnicodeEncodeError:
            # Skip games with problematic characters in their names
            continue

def save_sales_to_file(items, filename="steam_sales.json"):
    """Save the raw sales data to a file"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=4, ensure_ascii=False)
        print(f"✅ Sales data saved to '{filename}'")
    except IOError as e:
        print(f"❌ Error saving file: {e}")

def save_sales_to_text_file(items, filename="steam_sales.txt"):
    """Save sales data to a user-friendly text file sorted by discount percentage"""
    if not items or "results" not in items:
        print("❌ No valid data to save to text file")
        return False
    
    try:
        # Get all games and sort them by discount percentage
        all_games = items["results"]["all_games"]
        sorted_games = sort_items_by_discount(all_games)
        
        with open(filename, "w", encoding="utf-8") as f:
            # Write header
            f.write("==================================================\n")
            f.write("            STEAM SALES LİST                 \n")
            f.write("==================================================\n")
            f.write(f"Tarih: {items.get('search_date', time.strftime('%Y-%m-%d %H:%M:%S'))}\n")
            f.write(f"Toplam İndirimli Oyun Sayısı: {len(sorted_games)}\n\n")
            
            # Write section for each discount range
            ranges = [
                ("İNANILMAZ İNDİRİMLER (%90 - %100)", 90),
                ("BÜYÜK İNDİRİMLER (%80 - %89)", 80),
                ("İYİ İNDİRİMLER (%70 - %79)", 70),
                ("MAKUL İNDİRİMLER (%60 - %69)", 60),
                ("ORTA İNDİRİMLER (%50 - %59)", 50),
                ("KÜÇÜK İNDİRİMLER (%40 - %49)", 40),
                ("DİĞER İNDİRİMLER (<%40)", 0)
            ]
            
            for title, min_discount in ranges:
                max_discount = 100 if min_discount == 90 else min_discount + 9
                
                # Filter games in this discount range
                if min_discount == 0:
                    range_games = [g for g in sorted_games if g.get("discount_percent", 0) < 40]
                else:
                    range_games = [g for g in sorted_games if min_discount <= g.get("discount_percent", 0) <= max_discount]
                
                if range_games:
                    f.write("\n" + "=" * 50 + "\n")
                    f.write(f"{title} - {len(range_games)} Oyun\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for i, game in enumerate(range_games, 1):
                        name = game.get("name", "İsimsiz Oyun")
                        discount = game.get("discount_percent", 0)
                        original_price = format_price(game.get("original_price", 0))
                        final_price = format_price(game.get("final_price", 0))
                        app_id = game.get("id", "")
                        
                        f.write(f"{i}. Oyun Adı: {name}\n")
                        f.write(f"   İndirim Oranı: %{discount}\n")
                        f.write(f"   Orijinal Fiyatı: {original_price}\n")
                        f.write(f"   İndirimli Fiyatı: {final_price}\n")
                        if app_id:
                            f.write(f"   Link: https://store.steampowered.com/app/{app_id}\n")
                        f.write("\n")
        
        print(f"✅ User-friendly sales data saved to '{filename}'")
        return True
    except Exception as e:
        print(f"❌ Error saving text file: {e}")
        return False

def get_all_discounted_games(max_pages=50, results_interval=5):
    """Get as many discounted games as possible by scraping store pages, showing results every 5 pages"""
    all_items = []
    unique_items = []
    displayed_ids = set()  # Keep track of game IDs that have been displayed
    
    # Get games from store browse pages
    page = 1
    while page <= max_pages:
        batch_start_page = page
        batch_items = []  # Games found in this batch
        
        # Show batch progress header
        print(f"\nSearching pages {batch_start_page} to {min(batch_start_page + results_interval - 1, max_pages)}...")
        
        # Process a batch of pages
        for i in range(results_interval):
            if page > max_pages:
                break
                
            # Update progress bar
            progress = (i + 1) / results_interval
            print_progress_bar(i + 1, results_interval, 
                              prefix=f'Progress: Page {page}/{max_pages}', 
                              suffix=f'Complete ({page*100//max_pages}% Total)', 
                              length=50)
            
            html_content = fetch_store_search_page(page)
            
            if not html_content:
                print(f"\nFailed to fetch page {page}. Stopping.")
                page = max_pages + 1  # Exit the loop
                break
                
            page_results = extract_games_from_store_page(html_content)
            batch_items.extend(page_results)
            
            if not page_results:
                print(f"\nNo more games found on page {page}. Stopping.")
                page = max_pages + 1  # Exit the loop
                break
                
            all_items.extend(page_results)
            
            # Only print minimal progress status
            if i == results_interval - 1 or page == max_pages:
                print(f"\nFound {len(all_items)} games so far...")
            
            # Don't hammer the server too quickly
            if i < results_interval - 1 and page < max_pages:  # Don't sleep after the last page
                time.sleep(1.5)
                
            page += 1
        
        # After each batch of pages, remove duplicates
        seen_ids = set()
        unique_items = []
        for item in all_items:
            item_id = item.get("id")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_items.append(item)
        
        # New games in this batch
        new_batch_items = []
        for item in unique_items:
            item_id = item.get("id")
            if item_id and item_id not in displayed_ids:
                new_batch_items.append(item)
                displayed_ids.add(item_id)
        
        # Show intermediate results
        print(f"\n----- BATCH RESULTS -----")
        print(f"Total unique games found: {len(unique_items)}")
        print(f"New games in this batch: {len(new_batch_items)}")
        
        # Show only new games from this batch
        if new_batch_items:
            display_sales(new_batch_items, max_items=25, show_all=False, title="NEW GAMES FROM THIS BATCH")
            
            # Also show top games from the entire collection
            display_sales(unique_items, max_items=10, show_all=False, title="TOP OVERALL DISCOUNTS")
        else:
            print("\nNo new games found in this batch.")
            display_sales(unique_items, max_items=25, show_all=False)
        
        # Removed intermediate file saving
        
        # Pause between batches (15 seconds)
        print("\nContinuing automatically in 15 seconds...")
        for i in range(15, 0, -1):
            sys.stdout.write(f"\rContinuing in {i} seconds...")
            sys.stdout.flush()
            time.sleep(1)
        print("\nContinuing search...")
    
    return unique_items

def main():
    # ASCII art banner for Steam Sales Finder
    print("""
╔═══════════════════════════════════════════════╗
║   STEAM SALES FINDER - SALES FİNDER           ║
╚═══════════════════════════════════════════════╝
""")
    
    print("Fetching Steam sales with the best discounts...")
    print("Results will be shown every 5 pages and continue automatically.")
    print("Please wait while we search for deals...\n")
    
    # Define JSON filename with timestamp to avoid overwriting previous results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_filename = f"steam_sales_{timestamp}.json"
    text_filename = f"steam_sales_{timestamp}.txt"
    
    # Get all discounted games, showing results every 5 pages
    all_discounted_games = get_all_discounted_games(max_pages=50, results_interval=5)
    
    if all_discounted_games:
        # Create organized output
        organized_data = {
            "timestamp": timestamp,
            "total_games": len(all_discounted_games),
            "search_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": {
                "all_games": all_discounted_games,
                "by_discount": {}
            }
        }
        
        # Organize games by discount percentage ranges
        discount_ranges = {
            "90-100%": [],
            "80-89%": [],
            "70-79%": [],
            "60-69%": [],
            "50-59%": [],
            "40-49%": [],
            "30-39%": [],
            "20-29%": [],
            "10-19%": [],
            "1-9%": []
        }
        
        for game in all_discounted_games:
            discount = game.get("discount_percent", 0)
            if discount >= 90:
                discount_ranges["90-100%"].append(game)
            elif discount >= 80:
                discount_ranges["80-89%"].append(game)
            elif discount >= 70:
                discount_ranges["70-79%"].append(game)
            elif discount >= 60:
                discount_ranges["60-69%"].append(game)
            elif discount >= 50:
                discount_ranges["50-59%"].append(game)
            elif discount >= 40:
                discount_ranges["40-49%"].append(game)
            elif discount >= 30:
                discount_ranges["30-39%"].append(game)
            elif discount >= 20:
                discount_ranges["20-29%"].append(game)
            elif discount >= 10:
                discount_ranges["10-19%"].append(game)
            else:
                discount_ranges["1-9%"].append(game)
        
        # Add organized discount ranges to the output data
        organized_data["results"]["by_discount"] = discount_ranges
        
        # Add top discounts as a separate category
        top_discounts = sort_items_by_discount(all_discounted_games)[:50]  # Top 50 discounted games
        organized_data["results"]["top_discounts"] = top_discounts
        
        print(f"\n╔═══════════════════════════════════════════════╗")
        print(f"║  SEARCH COMPLETED!                           ║")
        print(f"║  Found {len(all_discounted_games)} unique discounted games.             ║")
        print(f"╚═══════════════════════════════════════════════╝")
        
        # Save final results with organized structure
        save_sales_to_file(organized_data, json_filename)
        
        # Save user-friendly text file
        save_sales_to_text_file(organized_data, text_filename)
        
        # Show final report without asking
        print("\nShowing all discovered games sorted by discount...")
        display_sales(all_discounted_games, show_all=True)
        
        print(f"\nSearch complete! Results are saved in:")
        print(f"  - JSON format: '{json_filename}'")
        print(f"  - Text format: '{text_filename}'")
    else:
        print("Could not fetch sales data. Please check your internet connection.")

if __name__ == "__main__":
    main() 