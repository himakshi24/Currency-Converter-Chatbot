from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# --- ⚙️ Configuration ---
# WARNING: In a production environment, use environment variables
# to secure your API key, e.g., os.getenv("API_KEY").
API_KEY = "fca_live_utemdrEM6W4gR99v6keBe2GSg2wEiOa6CvuI6nF7"
CURRENCY_API_BASE_URL = "https://api.currencyapi.com/v3/latest"


# ----------------------------------------------------------------------------


def fetch_conversion_factor(base_currency: str, target_currency: str) -> float | None:
    """
    Fetches the conversion rate from the external API.

    Calculates the rate (Source -> Target) by dividing
    Rate(Target/BaseCurrency) by Rate(Source/BaseCurrency), where the API's
    default base currency (usually USD) is used as the common denominator.

    Returns the conversion factor (rate) or None if the API call fails or rate is not found.
    """
    try:
        # Construct the API URL to fetch all rates relative to the API's base (default is USD)
        url = f"{CURRENCY_API_BASE_URL}?apikey={API_KEY}"

        # Make the request with a timeout
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        rates = data.get('data', {})

        # Currency codes must be uppercase to match the API response
        source_code = base_currency.upper()
        target_code = target_currency.upper()

        # Safely extract rates relative to the API's base currency
        target_rate_to_base = rates.get(target_code, {}).get('value')
        source_rate_to_base = rates.get(source_code, {}).get('value')

        if target_rate_to_base is not None and source_rate_to_base is not None and source_rate_to_base != 0:
            # Conversion factor: (Source -> Target) = Rate(Target/Base) / Rate(Source/Base)
            conversion_factor = target_rate_to_base / source_rate_to_base
            return conversion_factor

        print(f"Error: Could not find rates for {source_code} or {target_code} in API response.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


@app.route('/', methods=['POST'])
def index():
    """
    🚀 Webhook handler for currency conversion, designed to be called by Dialogflow.
    """
    try:
        data = request.get_json()

        # 1. Safely extract parameters from the Dialogflow JSON structure
        unit_currency_param = data.get('queryResult', {}).get('parameters', {}).get('unit-currency', {})
        source_currency = unit_currency_param.get('currency')
        amount = unit_currency_param.get('amount')
        target_currency = data.get('queryResult', {}).get('parameters', {}).get('currency-name')

        # 2. Validation
        if not all([source_currency, amount, target_currency]):
            return jsonify({
                "fulfillmentText": "Missing currency parameters. Please specify the amount, source, and target currencies."
            })

        # Ensure amount is a float
        try:
            amount = float(amount)
            amount = round(amount, 2)
        except ValueError:
            return jsonify({
                "fulfillmentText": "Invalid amount provided. Please use a numeric value."
            })

        # 3. Fetch conversion factor
        conversion_factor = fetch_conversion_factor(
            base_currency=source_currency,
            target_currency=target_currency
        )

        if conversion_factor is None:
            # Inform the user if the external service failed
            return jsonify({
                "fulfillmentText": f"I couldn't get the current conversion rate for {source_currency.upper()} to {target_currency.upper()}. The external currency service might be unavailable or the currency codes are unsupported."
            })

        # 4. Perform Calculation
        final_amount = amount * conversion_factor

        # 5. Create the fulfillment response
        response_text = (
            f"{amount:,.2f} {source_currency.upper()} is equal to "
            f"{final_amount:,.2f} {target_currency.upper()}. "
            f"(Rate: 1 {source_currency.upper()} = {conversion_factor:.4f} {target_currency.upper()})"
        )

        # 6. Return the structured response
        return jsonify({
            "fulfillmentText": response_text
        })

    except Exception as e:
        # Critical error handler
        print(f"Critical error in index route: {e}")
        # Return a generic error message to the user
        return jsonify({
            "fulfillmentText": "An internal error occurred while processing your request. Please try again later."
        })


if __name__ == '__main__':
    # Runs the Flask application on port 8080
    app.run(debug=True, port=8080)