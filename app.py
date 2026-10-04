from datetime import datetime, timedelta
import pandas as pd
import requests
import streamlit as st
from streamlit_qrcode_scanner import qrcode_scanner

# 1. METTEZ VOS LIENS ICI (laissez vide "" si vous n'avez pas l'un ou l'autre)
URL_LOGO = "https://www.centre-formation-securite.fr/wp-content/uploads/2018/11/logo-si2p-fond-clair.png"
URL_FOND = "https://www.centre-formation-securite.fr/wp-content/uploads/triangle-si2p.png"

# METTEZ ICI L'URL DE VOTRE APPLICATION WEB GOOGLE APPS SCRIPT :
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxjkfo7EsTGkc-CgWjRgNyZDxMnFeZewu3x0YNLGv0iGQI1siHMwFkZErAKmGkv-2nG/exec"

st.set_page_config(
    page_title="Gestion Extincteurs", page_icon="https://img.icons8.com/stickers/1200/fire-extinguisher.jpg", layout="centered"
)

# STYLE GLOBAL & TAILLE DES ÉCRITURES
st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-size: 18px; }
    .stButton>button { width: 100%; height: 3.5em; font-size: 20px; font-weight: bold; border-radius: 10px; }
    h1 { font-size: 32px !important; }
    h2 { font-size: 26px !important; }
    h3 { font-size: 22px !important; }
    </style>
""",
    unsafe_allow_html=True,
)


def get_data():
  try:
    response = requests.get(APPS_SCRIPT_URL + "?action=getData")
    data = response.json()
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


def update_batch(quantite, utilisateur, date):
  try:
    params = {
        "action": "updateBatch",
        "quantite": quantite,
        "utilisateur": utilisateur,
        "date": date,
    }
    response = requests.get(APPS_SCRIPT_URL, params=params)
    return response.json()
  except Exception as e:
    st.error(f"Erreur lors de la validation du lot : {e}")
    return None


# --- GESTION DES ÉTATS GLOBAUX ---
if "user" not in st.session_state:
  st.session_state.user = None
if "last_activity" not in st.session_state:
  st.session_state.last_activity = datetime.now()

# Registre global partagé pour empêcher les doubles connexions d'un même code
if "active_codes" not in st.session_state:
  st.session_state.active_codes = []

# --- VÉRIFICATION DE L'INACTIVITÉ (5 minutes) ---
INACTIVITY_LIMIT = timedelta(minutes=5)
if st.session_state.user is not None:
  if datetime.now() - st.session_state.last_activity > INACTIVITY_LIMIT:
    # Libérer le code de la liste des actifs
    code_actuel = str(st.session_state.user.get("Code"))
    if code_actuel in st.session_state.active_codes:
      st.session_state.active_codes.remove(code_actuel)

    st.session_state.user = None
    st.warning(
        "⏳ Session expirée suite à 5 minutes d'inactivité. Veuillez vous"
        " reconnecter."
    )
    st.rerun()
  else:
    # Met à jour l'heure de la dernière activité à chaque interaction
    st.session_state.last_activity = datetime.now()


# --- AUTHENTIFICATION ---
if st.session_state.user is None:
  st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQgi9peMxjPgEpbUU1SHhUBqaJa_GjKOId_5oPXARaqJw&s=10")
  st.title("🧯 Connexion")
  code_saisi = st.text_input("Code d'accès", type="password")

  if st.button("Se connecter"):
    if not code_saisi:
      st.error("Veuillez saisir un code.")
    elif str(code_saisi) in st.session_state.active_codes:
      st.error(
          "⚠️ Ce compte est déjà connecté sur un autre appareil ou une autre"
          " fenêtre !"
      )
    else:
      _, df_users = get_data()
      if df_users is not None:
        user_found = df_users[df_users["Code"].astype(str) == str(code_saisi)]
        if not user_found.empty:
          user_dict = user_found.iloc[0].to_dict()
          # Enregistre l'utilisateur et bloque son code
          st.session_state.user = user_dict
          st.session_state.active_codes.append(str(code_saisi))
          st.session_state.last_activity = datetime.now()
          st.rerun()
        else:
          st.error("Code d'accès incorrect.")
      else:
        st.error("Impossible de récupérer les utilisateurs.")

# --- INTERFACE SELON LE RÔLE ---
else:
  user = st.session_state.user
  st.sidebar.write(f"👤 **{user['Nom']}**")
  st.sidebar.write(f"🔑 Rôle : *{user['Role']}*")

  if st.sidebar.button("Se déconnecter"):
    # Libérer le code à la déconnexion
    code_actuel = str(user.get("Code"))
    if code_actuel in st.session_state.active_codes:
      st.session_state.active_codes.remove(code_actuel)

    st.session_state.user = None
    st.rerun()

  df_ext, _ = get_data()

  # FORMATEUR
  if str(user["Role"]).strip().lower() == "formateur":
    st.title("🧯 Formateur")
    st.write(
        "Scannez le QR code de l'extincteur."
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
          if nouveau_statut == "Vide":
            st.warning("📩 Un e-mail d'alerte a été envoyé au gestionnaire.")
        else:
          st.warning(f"⚠️ Cet extincteur est déjà au statut '{statut_actuel}'.")
      else:
        st.error(f"❌ L'ID '{id_scanne}' est introuvable.")

  # PRESTATAIRE
  elif str(user["Role"]).strip().lower() == "prestataire":
    st.image("https://thumbs.dreamstime.com/b/extincteur-avec-rendu-d-camion-isol%C3%A9-sur-fond-blanc-272191597.jpg")
    st.title("Prestataire")
    choix_action = st.radio(
        "Action :",
        (
            "Récupérer des extincteurs (Lot)",
            "Déposer / Rendre Plein (Scan individuel)",
        ),
    )

    if "Récupérer" in choix_action:
      vides = df_ext[df_ext["Statut"] == "Vide"]
      nb_vides = len(vides)
      st.info(f"📦 Extincteurs actuellement marqués 'Vide' : **{nb_vides}**")

      quantite_a_prendre = st.number_input(
          "Combien d'extincteurs le prestataire emporte-t-il ?",
          min_value=1,
          max_value=100,
          value=max(1, nb_vides),
      )

      if st.button("Valider le départ du lot"):
        date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        res = update_batch(quantite_a_prendre, user["Nom"], date_du_jour)
        if res and res.get("status") == "success":
          st.success(
              f"🚀 Départ validé pour {res.get('count')} extincteur(s). Un"
              " e-mail de suivi a été envoyé au gestionnaire."
          )
          st.rerun()

    else:
      st.write(
          "Scannez individuellement chaque extincteur de retour pour le"
          " basculer en **Plein**."
      )
      id_scanne_retour = qrcode_scanner(key="scanner_prestataire_retour")

      if id_scanne_retour:
        st.info(f"🔍 QR Code détecté : **{id_scanne_retour}**")
        mask = (
            df_ext["ID_Extincteur"].astype(str).str.strip().str.lower()
            == str(id_scanne_retour).strip().lower()
        )

        if mask.any():
          statut_actuel = df_ext.loc[mask, "Statut"].values[0]
          if statut_actuel in ["En rechargement", "Vide"]:
            date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_sheet(
                id_scanne_retour, "Plein", user["Nom"], date_du_jour
            )
            st.success(
                f"✅ Extincteur **{id_scanne_retour}** de retour et basculé en"
                " **Plein** !"
            )
          else:
            st.warning(f"⚠️ Cet extincteur est déjà au statut : {statut_actuel}")
        else:
          st.error("❌ ID introuvable.")
