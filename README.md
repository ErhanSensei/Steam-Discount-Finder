# Steam Sales Finder

A Python script that automatically searches and displays discounted games from the Steam store with detailed information.

## Features

- Automatically scans the latest Steam sales
- Sorts games by discount percentage
- Continuous, uninterrupted searching process
- Categorizes results by discount levels
- Displays game prices in USD
- Shows progress bar during search
- Saves results in both JSON format and a user-friendly text file

## Requirements

- Python 3.6 or newer
- Internet connection
- `requests` and `beautifulsoup4` libraries

## Installation

1. Clone this repository or download the files
2. Install the required libraries:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the script file:

```
python steam_sales.py
```

The program will automatically:
1. Start searching for discounted games on Steam
2. Show newly discovered games after every 5 pages
3. Wait 15 seconds between batches
4. Save the results when completed

## Output Files

The program creates two files when run:

1. `steam_sales_YYYYMMDD_HHMMSS.json` - Technical data in JSON format
2. `steam_sales_YYYYMMDD_HHMMSS.txt` - User-friendly report in text format

The text file lists games in the following format:

```
Game Name: Black Mesa
Discount: 90%
Original Price: $10.49
Sale Price: $1.04
Link: https://store.steampowered.com/app/362890
```

## Customization

You can modify the script to show prices in different currencies or search in different regional stores:

### Changing Region and Currency

In the `steam_sales.py` file, find and modify these parameters:

1. For searching in the US store (USD prices):
   - Find lines where `'cc': 'tr'` appears (around lines 40, 57, and 85)
   - Change `'tr'` to `'us'`

2. For searching in the UK store (GBP prices):
   - Change `'tr'` to `'uk'`

3. For other regions, use the appropriate country code:
   - `'fr'` - France (EUR)
   - `'de'` - Germany (EUR)
   - `'ru'` - Russia (RUB)
   - `'jp'` - Japan (JPY)
   - `'br'` - Brazil (BRL)
   - `'au'` - Australia (AUD)

### Changing Currency Display

To change how prices are displayed (currency symbol):
- Find the `format_price()` function (around line 340)
- Change the `$` symbol to the appropriate currency symbol (£, €, etc.)

### Changing Number of Pages to Search

To search more or fewer pages:
- In the `main()` function, find `all_discounted_games = get_all_discounted_games(max_pages=50, results_interval=5)`
- Change `max_pages=50` to your desired maximum number of pages

## Note

This script uses the Steam website and API. If Steam makes changes to their website structure, the script may need to be updated. 