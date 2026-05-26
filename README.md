# 📦 Digipad Downloader

**Digipad Downloader** est une application web locale open-source développée en Python (Flask) et Selenium. Elle permet d'analyser, d'extraire et de télécharger rapidement sous forme d'archive ZIP toutes les ressources contenues dans un mur collaboratif **Digipad** (proposé par *La Digitale*).

## ✨ Fonctionnalités

- 🔍 **Extraction Profonde :** Ne se contente pas des vignettes (images), le script simule des clics pour révéler et télécharger les véritables documents PDF, Word, Excel, etc.
- ⚡ **Téléchargement Ultra-Rapide :** Utilise le multi-threading pour télécharger plusieurs fichiers simultanément.
- 📂 **Respect de la Structure :** Les fichiers dans l'archive `.zip` finale sont automatiquement rangés dans des dossiers correspondant aux colonnes du Digipad.
- 🔐 **Gestion des Mots de Passe :** Capable d'analyser les Digipads privés si vous possédez le code d'accès.
- 💀 **Détection des Liens Morts :** Vérifie automatiquement la santé des liens externes (notamment les partages académiques *Nuage*) avant le téléchargement pour éviter les erreurs.
- 🌐 **Deux modes d'analyse :** Par lien URL direct (via Selenium) ou par injection du code source HTML (pour les accès très restreints).

## 🛠️ Prérequis

Pour faire fonctionner ce projet sur votre machine, vous devez avoir installé :
- **Python 3.8+**
- **Google Chrome** (Selenium l'utilisera en arrière-plan)

## 🚀 Installation

1. Clonez ce dépôt sur votre machine locale :
   ```bash
   git clone https://github.com/votre-pseudo/DigipadDownloader.git
   cd DigipadDownloader
   ```

2. Il est recommandé de créer un environnement virtuel :
   ```bash
   python -m venv venv
   # Sur Windows :
   venv\Scripts\activate
   # Sur macOS/Linux :
   source venv/bin/activate
   ```

3. Installez les dépendances requises :
   ```bash
   pip install -r requirements.txt
   ```

## 💻 Utilisation

1. Lancez le serveur Flask :
   ```bash
   python app.py
   ```

2. Ouvrez votre navigateur et rendez-vous à l'adresse suivante :
   **http://127.0.0.1:5000**

3. Collez l'URL de votre Digipad, saisissez le mot de passe si nécessaire, et cliquez sur **Analyser**.
4. Sélectionnez les fichiers que vous souhaitez conserver et cliquez sur **Télécharger la sélection (ZIP)**.

## ⚠️ Avertissement Légal & Éthique

**Ce projet a été créé à des fins strictement éducatives et pour un usage personnel (ex: sauvegarde locale de cours auxquels vous avez légitimement accès).**

- Le "scraping" (l'extraction automatisée de données) peut être contraire aux Conditions Générales d'Utilisation (CGU) de *La Digitale* ou des hébergeurs tiers.
- **Ne déployez pas ce projet sur un serveur web public.** Une utilisation massive depuis une seule adresse IP pourrait saturer les serveurs de l'association *La Digitale* (qui est un service gratuit et associatif) et entraîner un bannissement.
- Les auteurs et contributeurs de ce dépôt déclinent toute responsabilité en cas de mauvaise utilisation de cet outil, de violation des droits d'auteur ou d'infraction aux CGU des plateformes cibles.

## 🤝 Contribuer

Les contributions sont les bienvenues ! 
1. Forkez le projet
2. Créez votre branche (`git checkout -b feature/NouvelleFonctionnalite`)
3. Commitez vos changements (`git commit -m 'Ajout de la NouvelleFonctionnalite'`)
4. Pushez vers la branche (`git push origin feature/NouvelleFonctionnalite`)
5. Ouvrez une Pull Request

## 📄 Licence

**Tous droits réservés.** Ce code est fourni à des fins éducatives et d'usage personnel. Aucune licence open-source n'est accordée pour la redistribution ou la modification publique.

---
*Fait avec ❤️ pour simplifier la vie des étudiants et enseignants.*