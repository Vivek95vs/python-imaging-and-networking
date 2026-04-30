import pandas as pd
from googletrans import Translator

translator = Translator()

# Load the Excel file
xls_file = pd.read_excel("D:\\Dosisoft\\French isogray\\Dev_Chg_01 Cahier des charges Isogray V2.1 - V3.0.xls", sheet_name=None)

translated_sheets = {}

for sheet_name, df in xls_file.items():
    print(f"Translating sheet: {sheet_name}")
    translated_df = df.copy()

    for col in translated_df.columns:
        def safe_translate(x):
            if pd.isnull(x):
                return x
            try:
                translated = translator.translate(str(x), src='fr', dest='en')
                return translated.text if translated.text else x
            except Exception as e:
                print(f"Error translating '{x}': {e}")
                return x  # Return original if translation fails

        translated_df[col] = translated_df[col].apply(safe_translate)

    translated_sheets[sheet_name] = translated_df

# Save to a new Excel file
with pd.ExcelWriter("D:\\Dosisoft\\French isogray\\translated_file1.xlsx", engine='openpyxl') as writer:
    for sheet_name, translated_df in translated_sheets.items():
        translated_df.to_excel(writer, sheet_name=sheet_name, index=False)

print("✅ Translation complete! Saved as 'translated_file.xlsx'")
