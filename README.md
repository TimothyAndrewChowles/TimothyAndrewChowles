👋 Hi, I’m Timothy, AI & Finance major


## Property geocoding script

Use `geocode_properties.py` to fetch addresses and coordinates for a list of property names using the OpenStreetMap Nominatim service. The script is U.S.-centric by default but accepts any ISO country code.

Examples:

```bash
# Geocode properties from a file, writing results to CSV
python geocode_properties.py --file properties.txt --output results.csv

# Geocode a few names directly and print to stdout
python geocode_properties.py "Ascend at Chisholm Trail" "Ovation at Galatyn Park"

# Read from stdin and target a different country code
cat properties.txt | python geocode_properties.py --country ca
```
