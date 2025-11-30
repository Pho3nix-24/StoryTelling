import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

print("\n📌 Modelos disponibles para ESTA clave:\n")

models = genai.list_models()

for m in models:
    print(f"- {m.name} | soporta: {m.supported_generation_methods}")
