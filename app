import datetime
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
from streamlit_qrcode_scanner import qrcode_scanner

# CONFIGURATION DE LA PAGE
st.set_page_config(
    page_title="Gestion Extincteurs", page_icon="🧯", layout="centered"
)

# VOS IMAGES (Modifiez les liens si vous le souhaitez)
URL_LOGO = ""
URL_FOND = ""

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

# CONNEXION GOOGLE SHEETS
@st.cache_resource
def init_connection():
  scope = [
      "https://spreadsheets.google.com/feeds",
      "https://www.googleapis.com/auth/drive",
  ]
  try:
    if "gcp_service_account" in st.secrets:
      creds_dict = dict(st.secrets["gcp_service_account"])
      creds = ServiceAccountCredentials.from_json_keyfile_dict(
          creds_dict, scope
      )
    else:
      creds = ServiceAccountCredentials.from_json_keyfile_name(
          "credentials.json", scope
      )
    client = gspread.authorize(creds)
    # METTEZ LE NOM EXACT DE VOTRE GOOGLE SHEET ICI :
    sheet = client.open("Gestion_Extincteurs")
    return sheet
  except Exception as e:
    st.error(f"Erreur de connexion Google Sheets : {e}")
    return None


sheet = init_connection()


def get_data():
  if sheet is None:
    return None, None
  ws_ext = sheet.worksheet("Extincteurs")
  extincteurs = ws_ext.get_all_records()
  ws_users = sheet.worksheet("Utilisateurs")
  utilisateurs = ws_users.get_all_records()
  return extincteurs, utilisateurs


if "user" not in st.session_state:
  st.session_state.user = None

# AUTHENTIFICATION UNIQUE
if st.session_state.user is None:
  st.title("🧯 Connexion")
  st.write("Veuillez saisir votre code d'accès personnel.")
  code_saisi = st.text_input("Code d'accès", type="password")

  if st.button("Se connecter"):
    extincteurs, utilisateurs = get_data()
    if utilisateurs:
      user_found = next(
          (u for u in utilisateurs if str(u["Code"]) == str(code_saisi)), None
      )
      if user_found:
        st.session_state.user = user_found
        st.rerun()
      else:
        st.error("Code d'accès incorrect.")
    else:
      st.error("Impossible de récupérer la liste utilisateurs.")

# INTERFACE SELON LE RÔLE
else:
  user = st.session_state.user
  st.sidebar.write(f"👤 **{user['Nom']}**")
  st.sidebar.write(f"🔑 Rôle : *{user['Role']}*")

  if st.sidebar.button("Se déconnecter"):
    st.session_state.user = None
    st.rerun()

  extincteurs, _ = get_data()
  ws_ext = sheet.worksheet("Extincteurs")

  # FORMATEUR
  if user["Role"].lower() == "formateur":
    st.title("🧯 Mode Formateur")
    st.write(
        "Scannez le QR code de l'extincteur (Plein ➔ En formation ➔ Vide)."
    )

    id_scanne = qrcode_scanner(key="scanner_formateur")

    if id_scanne:
      st.info(f"🔍 QR Code détecté : **{id_scanne}**")
      row_index, ext_actuel = None, None
      for idx, ext in enumerate(extincteurs, start=2):
        if (
            str(ext["ID_Extincteur"]).strip().lower()
            == str(id_scanne).strip().lower()
        ):
          row_index = idx
          ext_actuel = ext
          break

      if ext_actuel and row_index:
        statut_actuel = ext_actuel["Statut"]
        if statut_actuel == "Plein":
          nouveau_statut = "En formation"
        elif statut_actuel == "En formation":
          nouveau_statut = "Vide"
        else:
          nouveau_statut = None

        if nouveau_statut:
          date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          ws_ext.update_cell(row_index, 2, nouveau_statut)
          ws_ext.update_cell(row_index, 3, user["Nom"])
          ws_ext.update_cell(row_index, 4, date_du_jour)
          st.success(
              f"✅ Extincteur **{ext_actuel['ID_Extincteur']}** mis à jour :"
              f" **{nouveau_statut}**"
          )
        else:
          st.warning(
              f"⚠️ Cet extincteur est déjà au statut '{statut_actuel}'"
              " (en attente de rechargement)."
          )
      else:
        st.error(
            f"❌ L'ID '{id_scanne}' est introuvable dans la base Google Sheets."
        )

  # PRESTATAIRE
  elif user["Role"].lower() == "prestataire":
    st.title("🚚 Mode Prestataire")
    choix_action = st.radio(
        "Que souhaitez-vous faire ?",
        (
            "Récupérer des extincteurs vides (Départ groupé)",
            "Déposer des extincteurs rechargés (Retour par scan)",
        ),
    )

    if "Récupérer" in choix_action:
      vides = [e for e in extincteurs if e["Statut"] == "Vide"]
      nb_vides = len(vides)
      st.info(
          f"📦 Il y a **{nb_vides}** extincteur(s) **Vide**(s) disponible(s)."
      )

      if nb_vides > 0:
        quantite = st.number_input(
            "Combien en emportez-vous ?",
            min_value=1,
            max_value=nb_vides,
            value=nb_vides,
        )
        if st.button("Valider le départ du lot"):
          date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          compteur = 0
          for idx, ext in enumerate(extincteurs, start=2):
            if ext["Statut"] == "Vide" and compteur < quantite:
              ws_ext.update_cell(idx, 2, "En rechargement")
              ws_ext.update_cell(idx, 3, user["Nom"])
              ws_ext.update_cell(idx, 4, date_du_jour)
              compteur += 1
          st.success(
              f"🚀 Départ validé pour {compteur} extincteur(s) (Passés"
              " 'En rechargement')."
          )
      else:
        st.warning("Aucun extincteur vide à récupérer.")
    else:
      st.write("Scannez un par un les extincteurs pour les rendre **Plein**.")
      id_scanne_retour = qrcode_scanner(key="scanner_prestataire")

      if id_scanne_retour:
        st.info(f"🔍 QR Code détecté : **{id_scanne_retour}**")
        row_index, ext_actuel = None, None
        for idx, ext in enumerate(extincteurs, start=2):
          if (
              str(ext["ID_Extincteur"]).strip().lower()
              == str(id_scanne_retour).strip().lower()
          ):
            row_index = idx
            ext_actuel = ext
            break

        if ext_actuel and row_index:
          if ext_actuel["Statut"] == "En rechargement":
            date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ws_ext.update_cell(row_index, 2, "Plein")
            ws_ext.update_cell(row_index, 3, user["Nom"])
            ws_ext.update_cell(row_index, 4, date_du_jour)
            st.success(
                f"✅ Extincteur **{ext_actuel['ID_Extincteur']}** de retour en"
                " stock (**Plein**)."
            )
          else:
            st.warning(
                f"⚠️ Cet extincteur n'est pas en rechargement (Statut :"
                f" {ext_actuel['Statut']})."
            )
        else:
          st.error(
              f"❌ L'ID '{id_scanne_retour}' est introuvable dans la base."
          )
