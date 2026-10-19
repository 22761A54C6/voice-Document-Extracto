"""Prompt sent to Gemini to turn a transcript into products. Fill with .format(text=...)."""

PRODUCT_EXTRACTION_PROMPT = """Extract every product from the transcribed text.

Rules:
- Associate each price with the correct product.
- Combine description lines belonging to the same product.
- Preserve all sizes and their prices as variants.
- Do not treat menu headings as products.
- Use numeric prices, not strings.
- Always include a description. If description is present in the text, use it. If not, write a short one (at most 12 words) based on the product name.
- Extract quantity/amount for the product if mentioned in the text (e.g., "2 burgers", "three cups"). If not mentioned, omit it.
- Extract quantity/amount for each variant if mentioned in the text. If not mentioned, omit it.
- Extract preparation time for the product if mentioned in the text (e.g., "10 minutes", "5 mins"). If not mentioned, omit it. Use integer representing minutes.
- IMPORTANT: Variants must be simple name-price pairs. Do NOT create nested variants (variants containing variants). Each variant should have only name, price, and quantity.
- Return ONLY minified JSON on a single line.

Use this structure:
{{"products":[{{"product_name":"string","description":"string","price":0,"quantity":0,"preparation_time":0,"variants":[{{"name":"string","price":0,"quantity":0}}]}}]}}

For products without variants, omit variants and set the product price.
For products with size-specific prices, use null for the product price and include all variants with their individual prices.


TRANSCRIBED TEXT:
{text}"""
