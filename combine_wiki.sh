ROOT="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$ROOT/all_wikipedia_content.md"
WIKI_DIR="$ROOT/data/wiki"

> "$OUTPUT"

find "$WIKI_DIR" -name "*.md" | sort | while read -r file; do
    echo "# $(basename "$file" .md)" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    cat "$file" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    echo "---" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
done

echo "Done: $OUTPUT"
