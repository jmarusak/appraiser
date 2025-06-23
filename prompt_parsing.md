Here is the valuation text: {{valuation_text}}

Your task is to parse this text into a JSON object that adheres to the **ValuationResponse** schema.

Provide detailed reasoning without linking that reasoning to the source information, such as "based on the image".

The **ValuationResponse** schema is:

{{valuation_schema}}

Ensure the resulting JSON is valid and contains the following fields:
- `estimated_value`
- `product_name`
- `reasoning`
- `search_urls`
