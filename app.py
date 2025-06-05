import streamlit as st
import pandas as pd
import requests
from collections import defaultdict

# Récupère le mot de passe depuis secrets.toml
APP_PASSWORD = st.secrets["general"]["app_password"]

st.set_page_config(page_title="Matching Leads", layout="wide")

# Initialisation du flag de connexion dans la session
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Affichage écran de connexion si pas connecté
if not st.session_state.logged_in:
    st.title("🔐 Connexion requise")
    password_input = st.text_input("Entrez le mot de passe", type="password")
    if st.button("Valider"):
        if password_input == APP_PASSWORD:
            st.session_state.logged_in = True
            st.success("Connexion réussie ! Vous pouvez maintenant utiliser l'application.")
        else:
            st.error("Mot de passe incorrect")

# Si connecté, on affiche le reste de l'application
if st.session_state.logged_in:
    # Chargement du fichier Excel
    excel_file = "exceldxb.xlsx"
    try:
        xls = pd.ExcelFile(excel_file)
        feuille_products = xls.parse("Products")
        feuille_sectors = xls.parse("Sectors")
        feuille_countries = xls.parse("Countries")
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier Excel : {e}")
        st.stop()

    # Fonction pour créer un mapping inversé (entreprise -> attributs)
    def construire_mapping(feuille):
        mapping = defaultdict(set)
        for col in feuille.columns:
            for val in feuille[col].dropna():
                mapping[val.strip()].add(col.strip())
        return mapping

    products_map = construire_mapping(feuille_products)
    sectors_map = construire_mapping(feuille_sectors)
    countries_map = construire_mapping(feuille_countries)

    # Regrouper tous les attributs par entreprise
    entreprises_attributs = defaultdict(lambda: {"Products": set(), "Sectors": set(), "Countries": set()})
    for entreprise, produits in products_map.items():
        entreprises_attributs[entreprise]["Products"] = produits
    for entreprise, secteurs in sectors_map.items():
        entreprises_attributs[entreprise]["Sectors"] = secteurs
    for entreprise, pays in countries_map.items():
        entreprises_attributs[entreprise]["Countries"] = pays

    # Mapping des champs personnalisés Pipedrive
    CUSTOM_FIELD_MAP = {
        "56410da7410b4a607ec34d0891c43678294f74dc": "Products",
        "0144bcc78cc774d8675c881b6f97499753c60a06": "Sectors",
        "ac6b557eb070b9f9fca5e6527cda1980b10e6694": "Countries"
    }

    # Onglets
    onglets = st.tabs(["🗂️ Données Excel", "🔗 Connexion Pipedrive", "🔍 Recherche"])

    with onglets[0]:
        st.title("🗂️ Données Excel")
        st.subheader("📄 Feuille Products")
        st.dataframe(feuille_products)
        st.subheader("📄 Feuille Sectors")
        st.dataframe(feuille_sectors)
        st.subheader("📄 Feuille Countries")
        st.dataframe(feuille_countries)

    with onglets[1]:
        st.title("🔗 Connexion à Pipedrive")
        api_token = st.text_input("Entre ton API token Pipedrive", type="password")
        if api_token:
            st.success("✅ Clé enregistrée avec succès")
            st.session_state["API_TOKEN"] = api_token

    with onglets[2]:
        st.title("🔍 Recherche de correspondances")

        if "API_TOKEN" not in st.session_state:
            st.warning("Veuillez d'abord entrer et enregistrer votre API token dans l'onglet Pipedrive.")
        else:
            API_TOKEN = st.session_state["API_TOKEN"]
            BASE_URL = "https://api.pipedrive.com/v1"

            def get_leads():
                url = f"{BASE_URL}/leads?api_token={API_TOKEN}"
                response = requests.get(url)
                if response.status_code == 200:
                    return response.json().get("data", [])
                return []

            leads = get_leads()
            lead_titles = [lead.get("title") for lead in leads if lead.get("title")]

            if not lead_titles:
                st.info("Aucun lead trouvé ou token invalide.")
            else:
                selected_lead = st.selectbox("🔍 Nom du prospect", lead_titles)

                def get_lead_details(lead_obj):
                    tags = {"Products": [], "Sectors": [], "Countries": []}
                    for field_id, value in lead_obj.items():
                        if field_id in CUSTOM_FIELD_MAP:
                            champ = CUSTOM_FIELD_MAP[field_id]
                            tags[champ].append(value)
                    return tags

                lead_data = next((lead for lead in leads if lead.get("title") == selected_lead), None)

                if lead_data:
                    tags = get_lead_details(lead_data)
                    st.subheader("📌 Attributs du lead")
                    if any(tags.values()):
                        for key, values in tags.items():
                            st.write(f"**{key}**: {', '.join(values) if values else 'Aucun'}")
                    else:
                        st.write("Aucun attribut renseigné pour ce lead.")

                    # Recherche de correspondances
                    resultats = set()    
                    for entreprise, attributs in entreprises_attributs.items():
                        if (
                            attributs["Products"] & set(tags["Products"]) or
                            attributs["Sectors"] & set(tags["Sectors"]) or
                            attributs["Countries"] & set(tags["Countries"])
                        ):
                            resultats.add(entreprise)

                    st.subheader("🔎 Résultat de la recherche")
                    if resultats:
                        st.success("✅ Fonds/entreprises avec au moins un attribut en commun :")
                        st.write(sorted(resultats))
                    else:
                        st.warning("Aucune entreprise ne correspond à ce lead.")
                else:
                    st.warning("Lead introuvable.")
