ROOT="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$ROOT/all_csv_content_dark_souls_3.txt"
DATA_DIR="$ROOT/data"

> "$OUTPUT"

find "$DATA_DIR" -maxdepth 1 -name "*.csv" | sort | while read -r file; do
    name=$(basename "$file" .csv)
    echo "== $name ==" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    cat "$file" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
done

echo "Done: $OUTPUT"
