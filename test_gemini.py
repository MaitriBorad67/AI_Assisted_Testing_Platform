
import tomllib
from pathlib import Path
from google import genai

secrets_file = Path(".streamlit/secrets.toml")

if not secrets_file.exists():
    print("Secrets file not found.")
else:
    with open(secrets_file, "rb") as file:
        secrets = tomllib.load(file)

    api_key = secrets.get("GEMINI_API_KEY")

    if not api_key:
        print("API key not found.")
    else:
        client = genai.Client(api_key=api_key)

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents="Reply with: Gemini connection successful."
            )

            print(response.text)

        except Exception as error:
            print("Connection failed:", type(error).__name__)
            print(error)

        finally:
            client.close()
