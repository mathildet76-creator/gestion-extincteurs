from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from streamlit_qrcode_scanner import qrcode_scanner

# 1. METTEZ VOS LIENS ICI (laissez vide "" si vous n'avez pas l'un ou l'autre)
URL_LOGO = "https://www.google.com/imgres?q=logo%20SI2P%20normandie&imgurl=https%3A%2F%2Fmedia.licdn.com%2Fdms%2Fimage%2Fv2%2FC4D0BAQE0nv_-BSrbeg%2Fcompany-logo_200_200%2Fcompany-logo_200_200%2F0%2F1630554654853%2Fsi2p_logo%3Fe%3D2147483647%26v%3Dbeta%26t%3DDhI1piKe4kAF-SLWOveCyeOPptA6YqDYHyc0LInWIu0&imgrefurl=https%3A%2F%2Fke.linkedin.com%2Fcompany%2Fsi2p&docid=-8H1BSUZY6hJdM&tbnid=PygHN-76uhZt8M&vet=12ahUKEwjE-Puey56XAxV_UaQEHebfIEcQnPAOegUImgEQAA..i&w=200&h=200&hcb=2&itg=1&ved=2ahUKEwjE-Puey56XAxV_UaQEHebfIEcQnPAOegUImgEQAA"
URL_FOND = "https://www.google.com/url?sa=t&source=web&rct=j&url=https%3A%2F%2Fozdistra.tn%2Fextincteur%2Fextincteur-co2-2kg-ce-229.html&ved=0CBcQjRxqGAoTCMjau8nJnpcDFQAAAAAdAAAAABC3AQ&opi=89978449"

# METTEZ ICI L'URL DE VOTRE APPLICATION WEB GOOGLE APPS SCRIPT :
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxjkfo7EsTGkc-CgWjRgNyZDxMnFeZewu3x0YNLGv0iGQI1siHMwFkZErAKmGkv-2nG/exec"

st.set_page_config(
    page_title="Gestion Extincteurs", page_icon="🧯", layout="centered"
)

# 2. APPLICATION DU STYLE (IMAGE DE FOND ET BOUTONS)
st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: linear-gradient(rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.9)), url("{URL_FOND}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}
    .stButton>button {{
        width: 100%;
        height: 3em;
        font-size: 18px;
        font-weight: bold;
        border-radius: 10px;
    }}
    </style>
""",
    unsafe_allow_html=True,
)

# 3. AFFICHAGE DU LOGO DANS LA BARRE LATÉRALE (optionnel)
if URL_LOGO:
  st.sidebar.image(URL_LOGO, use_container_width=True)


def get_data():
  try:
    response = requests.get(APPS_SCRIPT_URL + "?action=getData")
    data = response.json()
    # Conversion des tableaux Google Sheets en DataFrames Pandas
    df_ext = pd.DataFrame(data["extincteurs"][1:], columns=data["extincteurs"][0])
    df_users = pd.DataFrame(
        data["utilisateurs"][1:], columns=data["utilisateurs"][0]
    )
    return df_ext, df_users
  except Exception as e:
    st.error(f"Erreur de communication avec Google Sheets : {e}")
    return None, None


def update_sheet(id_ext, statut, utilisateur, date):
  try:
    params = {
        "action": "update",
        "id": id_ext,
        "statut": statut,
        "utilisateur": utilisateur,
        "date": date,
    }
    requests.get(APPS_SCRIPT_URL, params=params)
  except Exception as e:
    st.error(f"Erreur lors de la mise à jour : {e}")


if "user" not in st.session_state:
  st.session_state.user = None

# AUTHENTIFICATION
if st.session_state.user is None:
  st.title("🧯 Connexion")
  code_saisi = st.text_input("Code d'accès", type="password")

  if st.button("Se connecter"):
    _, df_users = get_data()
    if df_users is not None:
      user_found = df_users[df_users["Code"].astype(str) == str(code_saisi)]
      if not user_found.empty:
        st.session_state.user = user_found.iloc[0].to_dict()
        st.rerun()
      else:
        st.error("Code d'accès incorrect.")
    else:
      st.error("Impossible de récupérer les utilisateurs.")

# INTERFACE SELON LE RÔLE
else:
  user = st.session_state.user
  st.sidebar.write(f"👤 **{user['Nom']}**")
  st.sidebar.write(f"🔑 Rôle : *{user['Role']}*")

  if st.sidebar.button("Se déconnecter"):
    st.session_state.user = None
    st.rerun()

  df_ext, _ = get_data()

  # FORMATEUR
  if str(user["Role"]).strip().lower() == "formateur":
    st.title("🧯 Mode Formateur")
    st.write(
        "Scannez le QR code de l'extincteur (Plein ➔ En formation ➔ Vide)."
    )

    id_scanne = qrcode_scanner(key="scanner_formateur")

    if id_scanne:
      st.info(f"🔍 QR Code détecté : **{id_scanne}**")
      mask = (
          df_ext["ID_Extincteur"].astype(str).str.strip().str.lower()
          == str(id_scanne).strip().lower()
      )

      if mask.any():
        statut_actuel = df_ext.loc[mask, "Statut"].values[0]
        if statut_actuel == "Plein":
          nouveau_statut = "En formation"
        elif statut_actuel == "En formation":
          nouveau_statut = "Vide"
        else:
          nouveau_statut = None

        if nouveau_statut:
          date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          update_sheet(id_scanne, nouveau_statut, user["Nom"], date_du_jour)
          st.success(
              f"✅ Extincteur **{id_scanne}** mis à jour : **{nouveau_statut}**"
          )
        else:
          st.warning(f"⚠️ Cet extincteur est déjà au statut '{statut_actuel}'.")
      else:
        st.error(f"❌ L'ID '{id_scanne}' est introuvable.")

  # PRESTATAIRE
  elif str(user["Role"]).strip().lower() == "prestataire":
    st.title("🚚 Mode Prestataire")
    choix_action = st.radio(
        "Action :",
        (
            "Récupérer des extincteurs vides",
            "Déposer des extincteurs rechargés",
        ),
    )

    if "Récupérer" in choix_action:
      vides = df_ext[df_ext["Statut"] == "Vide"]
      nb_vides = len(vides)
      st.info(f"📦 Il y a **{nb_vides}** extincteur(s) vide(s).")

      if nb_vides > 0:
        quantite = st.number_input(
            "Combien en emportez-vous ?",
            min_value=1,
            max_value=nb_vides,
            value=nb_vides,
        )
        if st.button("Valider le départ"):
          date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          indices_vides = df_ext[df_ext["Statut"] == "Vide"].index[
              :int(quantite)
          ]
          for idx in indices_vides:
            ext_id = df_ext.loc[idx, "ID_Extincteur"]
            update_sheet(ext_id, "En rechargement", user["Nom"], date_du_jour)
          st.success(
              f"🚀 Départ validé pour {len(indices_vides)} extincteur(s)."
          )
      else:
        st.warning("Aucun extincteur vide.")
    else:
      st.write("Scannez pour rendre **Plein**.")
      id_scanne_retour = qrcode_scanner(key="scanner_prestataire")

      if id_scanne_retour:
        st.info(f"🔍 QR Code détecté : **{id_scanne_retour}**")
        mask = (
            df_ext["ID_Extincteur"].astype(str).str.strip().str.lower()
            == str(id_scanne_retour).strip().lower()
        )

        if mask.any():
          statut_actuel = df_ext.loc[mask, "Statut"].values[0]
          if statut_actuel == "En rechargement":
            date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_sheet(
                id_scanne_retour, "Plein", user["Nom"], date_du_jour
            )
            st.success(
                f"✅ Extincteur **{id_scanne_retour}** de retour (**Plein**)."
            )
          else:
            st.warning(f"⚠️ Statut actuel non valide : {statut_actuel}")
        else:
          st.error("❌ ID introuvable.")
