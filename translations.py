import json
from pathlib import Path
import locale
import os

# Configuración de Rutas
STORE_DIR = Path.home() / '.local' / 'share' / 'yelena-store'
CONFIG_FILE = STORE_DIR / 'config.json'
STORE_DIR.mkdir(parents=True, exist_ok=True)

# Diccionario de traducciones (ES, EN, PT, CA, IT, DE)
# 'key': {'es': 'Traducción en Español', 'en': 'English Translation', 'pt': 'Tradução em Português', 'ca': 'Català Translation', 'it': 'Italiano Translation', 'de': 'Deutsch Translation'}
TRANSLATIONS = {
    # Ventana Principal
    "Yelena Store": {"es": "Yelena Store", "en": "Yelena Store", "pt": "Yelena Store", "ca": "Yelena Store", "it": "Yelena Store", "de": "Yelena Store"},
    "Software Manager": {"es": "Gestor de Software", "en": "Software Manager", "pt": "Gerenciador de Software", "ca": "Gestor de Programari", "it": "Gestore Software", "de": "Software-Manager"},
    "Search": {"es": "Buscar", "en": "Search", "pt": "Buscar", "ca": "Cerca", "it": "Cerca", "de": "Suchen"},
    "Search applications...": {"es": "Buscar aplicaciones...", "en": "Search applications...", "pt": "Buscar aplicativos...", "ca": "Cerca aplicacions...", "it": "Cerca applicazioni...", "de": "Anwendungen suchen..."},
    "Categories": {"es": "Categorías", "en": "Categories", "pt": "Categorias", "ca": "Categories", "it": "Categorie", "de": "Kategorien"},
    "About": {"es": "Acerca de", "en": "About", "pt": "Sobre", "ca": "Quant a", "it": "Informazioni", "de": "Über"},
    "Ready": {"es": "Listo", "en": "Ready", "pt": "Pronto", "ca": "A punt", "it": "Pronto", "de": "Bereit"},
    "Back": {"es": "Atrás", "en": "Back", "pt": "Voltar", "ca": "Enrere", "it": "Indietro", "de": "Zurück"},
    "Home": {"es": "Inicio", "en": "Home", "pt": "Início", "ca": "Inici", "it": "Home", "de": "Startseite"},
    "Change Language": {"es": "Cambiar Idioma", "en": "Change Language", "pt": "Mudar Idioma", "ca": "Canviar Idioma", "it": "Cambia Lingua", "de": "Sprache ändern"},
    "Tasks": {"es": "Tareas", "en": "Tasks", "pt": "Tarefas", "ca": "Tasques", "it": "Attività", "de": "Aufgaben"},
    "Updates": {"es": "Actualizaciones", "en": "Updates", "pt": "Atualizações", "ca": "Actualitzacions", "it": "Aggiornamenti", "de": "Updates"},
    "The updates manager (cuerdtoken) is not installed or not in PATH.": {"es": "El gestor de actualizaciones (cuerdtoken) no está instalado o no se encuentra en PATH.", "en": "The updates manager (cuerdtoken) is not installed or not in PATH.", "pt": "O gerenciador de atualizações (cuerdtoken) não está instalado ou não está no PATH.", "ca": "El gestor d'actualitzacions (cuerdtoken) no està instal·lat o no es troba al PATH.", "it": "Il gestore degli aggiornamenti (cuerdtoken) non è installato o non è nel PATH.", "de": "Der Update-Manager (cuerdtoken) ist nicht installiert oder nicht im PATH."},
    "Updates Manager Not Found": {"es": "Gestor de Actualizaciones No Encontrado", "en": "Updates Manager Not Found", "pt": "Gerenciador de Atualizações Não Encontrado", "ca": "Gestor d'Actualitzacions No Trobat", "it": "Gestore Aggiornamenti Non Trovato", "de": "Update-Manager nicht gefunden"},
    "Opening Updates Manager...": {"es": "Abriendo Gestor de Actualizaciones...", "en": "Opening Updates Manager...", "pt": "Abrindo Gerenciador de Atualizações...", "ca": "Obrint Gestor d'Actualitzacions...", "it": "Apertura Gestore Aggiornamenti...", "de": "Update-Manager wird geöffnet..."},
    "Updates Manager not available": {"es": "Gestor de Actualizaciones no disponible", "en": "Updates Manager not available", "pt": "Gerenciador de Atualizações não disponível", "ca": "Gestor d'Actualitzacions no disponible", "it": "Gestore Aggiornamenti non disponibile", "de": "Update-Manager nicht verfügbar"},
    "The updates manager (cuerdtoken) is not installed or not in PATH.": {"es": "El gestor de actualizaciones (cuerdtoken) no está instalado o no se encuentra en PATH.", "en": "The updates manager (cuerdtoken) is not installed or not in PATH.", "pt": "O gerenciador de atualizações (cuerdtoken) não está instalado ou não está no PATH.", "ca": "El gestor d'actualitzacions (cuerdtoken) no està instal·lat o no es troba al PATH.", "it": "Il gestore degli aggiornamenti (cuerdtoken) non è installato o non è nel PATH.", "de": "Der Update-Manager (cuerdtoken) ist nicht installiert oder nicht im PATH."},


    # Diálogo de Cierre
    "The pending tasks will be canceled.": {"es": "Las tareas pendientes serán canceladas.", "en": "The pending tasks will be canceled.", "pt": "As tarefas pendentes serão canceladas.", "ca": "Les tasques pendents seran cancel·lades.", "it": "Le attività in sospeso saranno annullate.", "de": "Anstehende Aufgaben werden abgebrochen."},
    "There are active installation or uninstallation tasks. Closing the program will cancel all of them. Do you want to continue?": {"es": "Hay tareas activas de instalación o desinstalación. Cerrar el programa cancelará todas ellas. ¿Desea continuar?", "en": "There are active installation or uninstallation tasks. Closing the program will cancel all of them. Do you want to continue?", "pt": "Há tarefas ativas de instalação ou desinstalação. Fechar o programa cancelará todas elas. Deseja continuar?", "ca": "Hi ha tasques d'instal·lació o desinstal·lació actives. Tancar el programa les cancel·larà totes. Voleu continuar?", "it": "Ci sono attività attive di installazione o disinstallazione. Chiudere il programma le annullerà tutte. Vuoi continuare?", "de": "Es gibt aktive Installations- oder Deinstallationsaufgaben. Das Schließen des Programms bricht alle ab. Möchten Sie fortfahren?"},
    
    # Home y Categorías
    "Explore Categories": {"es": "Explorar Categorías", "en": "Explore Categories", "pt": "Explorar Categorias", "ca": "Explorar Categories", "it": "Esplora Categorie", "de": "Kategorien erkunden"},
    "All Applications": {"es": "Todas las Aplicaciones", "en": "All Applications", "pt": "Todos os Aplicativos", "ca": "Totes les Aplicacions", "it": "Tutte le Applicazioni", "de": "Alle Anwendungen"},
    "Popular Applications": {"es": "Aplicaciones Populares", "en": "Popular Applications", "pt": "Aplicativos Populares", "ca": "Aplicacions Populars", "it": "Applicazioni Popolari", "de": "Beliebte Anwendungen"},
    "Flatpak Applications": {"es": "Aplicaciones Flatpak", "en": "Flatpak Applications", "pt": "Aplicativos Flatpak", "ca": "Aplicacions Flatpak", "it": "Applicazioni Flatpak", "de": "Flatpak-Anwendungen"},
    "Results from catalog": {"es": "Resultados del catálogo", "en": "Results from catalog", "pt": "Resultados do catálogo", "ca": "Resultats del catàleg", "it": "Risultati dal catalogo", "de": "Ergebnisse aus dem Katalog"},
    "Searching in catalog...": {"es": "Buscando en el catálogo...", "en": "Searching in catalog...", "pt": "Procurando no catálogo...", "ca": "Cercant al catàleg...", "it": "Ricerca nel catalogo...", "de": "Suche im Katalog..."},
    "Searching in repositories...": {"es": "Buscando en repositorios...", "en": "Searching in repositories...", "pt": "Procurando em repositórios...", "ca": "Cercant en repositoris...", "it": "Ricerca nei repository...", "de": "Suche in Repositories..."},
    "Waiting for APT lock...": {"es": "Esperando bloqueo de APT...", "en": "Waiting for APT lock...", "pt": "Aguardando bloqueio do APT...", "ca": "Esperant bloqueig d'APT...", "it": "In attesa del blocco APT...", "de": "Warten auf APT-Sperre..."},
    "Closing Yelena Store": {"es": "Cerrando Yelena Store", "en": "Closing Yelena Store", "pt": "Fechando Yelena Store", "ca": "Tancant Yelena Store", "it": "Chiusura Yelena Store", "de": "Yelena Store wird geschlossen"},
    "Please wait...": {"es": "Por favor espere...", "en": "Please wait...", "pt": "Por favor aguarde...", "ca": "Si us plau, espereu...", "it": "Attendere prego...", "de": "Bitte warten..."},
    "Unverified Application": {"es": "Aplicación No Verificada", "en": "Unverified Application", "pt": "Aplicativo Não Verificado", "ca": "Aplicació No Verificada", "it": "Applicazione Non Verificata", "de": "Nicht verifizierte Anwendung"},
    "This application is not verified. Install at your own risk.": {"es": "Esta aplicación no está verificada. Instalar bajo su propio riesgo.", "en": "This application is not verified. Install at your own risk.", "pt": "Este aplicativo não está verificado. Instale por sua conta e risco.", "ca": "Aquesta aplicació no està verificada. Instal·leu sota el vostre propi risc.", "it": "Questa applicazione non è verificata. Installare a proprio rischio.", "de": "Diese Anwendung ist nicht verifiziert. Auf eigene Gefahr installieren."},
    "Verified by Flathub": {"es": "Verificado por Flathub", "en": "Verified by Flathub", "pt": "Verificado pelo Flathub", "ca": "Verificat per Flathub", "it": "Verificato da Flathub", "de": "Von Flathub verifiziert"},
    "Unverified source": {"es": "Fuente no verificada", "en": "Unverified source", "pt": "Fonte não verificada", "ca": "Font no verificada", "it": "Fonte non verificata", "de": "Nicht verifizierte Quelle"},
    "Package ID": {"es": "ID del Paquete", "en": "Package ID", "pt": "ID do Pacote", "ca": "ID del Paquet", "it": "ID Pacchetto", "de": "Paket-ID"},
    "Remote": {"es": "Remoto", "en": "Remote", "pt": "Remoto", "ca": "Remot", "it": "Remoto", "de": "Remote"},
    "Initializing search...": {"es": "Inicializando búsqueda...", "en": "Initializing search...", "pt": "Inicializando pesquisa...", "ca": "Inicialitzant cerca...", "it": "Inizializzazione ricerca...", "de": "Suche wird initialisiert..."},
    "Searching in APT repositories...": {"es": "Buscando en repositorios APT...", "en": "Searching in APT repositories...", "pt": "Procurando em repositórios APT...", "ca": "Cercant en repositoris APT...", "it": "Ricerca nei repository APT...", "de": "Suche in APT-Repositories..."},
    "Searching in Flatpak repositories...": {"es": "Buscando en repositorios Flatpak...", "en": "Searching in Flatpak repositories...", "pt": "Procurando em repositórios Flatpak...", "ca": "Cercant en repositoris Flatpak...", "it": "Ricerca nei repository Flatpak...", "de": "Suche in Flatpak-Repositories..."},
    "APT search complete": {"es": "Búsqueda APT completa", "en": "APT search complete", "pt": "Pesquisa APT concluída", "ca": "Cerca APT completa", "it": "Ricerca APT completata", "de": "APT-Suche abgeschlossen"},
    "Flatpak search complete": {"es": "Búsqueda Flatpak completa", "en": "Flatpak search complete", "pt": "Pesquisa Flatpak concluída", "ca": "Cerca Flatpak completa", "it": "Ricerca Flatpak completata", "de": "Flatpak-Suche abgeschlossen"},
    "Processing results...": {"es": "Procesando resultados...", "en": "Processing results...", "pt": "Processando resultados...", "ca": "Processant resultats...", "it": "Elaborazione risultati...", "de": "Ergebnisse werden verarbeitet..."},
    "Finalizing...": {"es": "Finalizando...", "en": "Finalizing...", "pt": "Finalizando...", "ca": "Finalitzant...", "it": "Finalizzazione...", "de": "Abschluss..."},
    "Search complete!": {"es": "¡Búsqueda completa!", "en": "Search complete!", "pt": "Pesquisa concluída!", "ca": "Cerca completa!", "it": "Ricerca completata!", "de": "Suche abgeschlossen!"},
    "packages found": {"es": "paquetes encontrados", "en": "packages found", "pt": "pacotes encontrados", "ca": "paquets trobats", "it": "pacchetti trovati", "de": "Pakete gefunden"},
    "Closing": {"es": "Cerrando", "en": "Closing", "pt": "Fechando", "ca": "Tancant", "it": "Chiusura", "de": "Schließen"},
    "Canceled": {"es": "Cancelado", "en": "Canceled", "pt": "Cancelado", "ca": "Cancel·lat", "it": "Annullato", "de": "Abgebrochen"},

    # Categorías
    "Development": {"es": "Desarrollo", "en": "Development", "pt": "Desenvolvimento", "ca": "Desenvolupament", "it": "Sviluppo", "de": "Entwicklung"},
    "Multimedia": {"es": "Multimedia", "en": "Multimedia", "pt": "Multimídia", "ca": "Multimèdia", "it": "Multimedia", "de": "Multimedia"},
    "Games": {"es": "Juegos", "en": "Games", "pt": "Jogos", "ca": "Jocs", "it": "Giochi", "de": "Spiele"},
    "Office": {"es": "Oficina", "en": "Office", "pt": "Escritório", "ca": "Oficina", "it": "Ufficio", "de": "Büro"},
    "Internet": {"es": "Internet", "en": "Internet", "pt": "Internet", "ca": "Internet", "it": "Internet", "de": "Internet"},
    "Graphics": {"es": "Gráficos", "en": "Graphics", "pt": "Gráficos", "ca": "Gràfics", "it": "Grafica", "de": "Grafik"},
    "Utilities": {"es": "Utilidades", "en": "Utilities", "pt": "Utilitários", "ca": "Utilitats", "it": "Utilità", "de": "Dienstprogramme"},
    "System": {"es": "Sistema", "en": "System", "pt": "Sistema", "ca": "Sistema", "it": "Sistema", "de": "System"},
    
    # Búsqueda
    "Searching packages...": {"es": "Buscando paquetes...", "en": "Searching packages...", "pt": "Procurando pacotes...", "ca": "Cercant paquets...", "it": "Ricerca pacchetti in corso...", "de": "Pakete werden gesucht..."},
    "This may take a few seconds": {"es": "Esto puede tardar unos segundos", "en": "This may take a few seconds", "pt": "Isso pode levar alguns segundos", "ca": "Això pot trigar uns segons", "it": "Questo potrebbe richiedere alcuni secondi", "de": "Dies kann einige Sekunden dauern"},
    "Searching": {"es": "Buscando", "en": "Searching", "pt": "Procurando", "ca": "Cercant", "it": "Ricerca", "de": "Suchen"},
    "No results found": {"es": "No se encontraron resultados", "en": "No results found", "pt": "Nenhum resultado encontrado", "ca": "No s'han trobat resultats", "it": "Nessun risultato trovato", "de": "Keine Ergebnisse gefunden"},
    "Try a different search term": {"es": "Pruebe un término de búsqueda diferente", "en": "Try a different search term", "pt": "Tente um termo de busca diferente", "ca": "Proveu un terme de cerca diferent", "it": "Prova un termine di ricerca diverso", "de": "Versuchen Sie einen anderen Suchbegriff"},
    "results for": {"es": "resultados para", "en": "results for", "pt": "resultados para", "ca": "resultats per", "it": "risultati per", "de": "Ergebnisse für"},
    "results": {"es": "resultados", "en": "results", "pt": "resultados", "ca": "resultats", "it": "risultati", "de": "Ergebnisse"},
    
    # Pantalla de Carga
    "Application Manager": {"es": "Gestor de Aplicaciones", "en": "Application Manager", "pt": "Gerenciador de Aplicativos", "ca": "Gestor d'Aplicacions", "it": "Gestore Applicazioni", "de": "Anwendungsmanager"},
    "Loading catalog...": {"es": "Cargando catálogo...", "en": "Loading catalog...", "pt": "Carregando catálogo...", "ca": "Carregant catàleg...", "it": "Caricamento catalogo...", "de": "Katalog wird geladen..."},
    "Please wait while we prepare everything": {"es": "Por favor espere mientras preparamos todo", "en": "Please wait while we prepare everything", "pt": "Por favor aguarde enquanto preparamos tudo", "ca": "Si us plau, espereu mentre ho preparem tot", "it": "Attendere mentre prepariamo tutto", "de": "Bitte warten Sie, während wir alles vorbereiten"},
    "Error loading catalog": {"es": "Error al cargar catálogo", "en": "Error loading catalog", "pt": "Erro ao carregar catálogo", "ca": "Error en carregar el catàleg", "it": "Errore nel caricamento del catalogo", "de": "Fehler beim Laden des Katalogs"},
    "Retry": {"es": "Reintentar", "en": "Retry", "pt": "Tentar novamente", "ca": "Tornar a intentar", "it": "Riprova", "de": "Erneut versuchen"},
    "Initializing managers...": {"es": "Inicializando gestores...", "en": "Initializing managers...", "pt": "Inicializando gerenciadores...", "ca": "Inicialitzant gestors...", "it": "Inizializzazione gestori...", "de": "Manager werden initialisiert..."},
    "Setting up activity monitor...": {"es": "Configurando monitor de actividad...", "en": "Setting up activity monitor...", "pt": "Configurando monitor de atividade...", "ca": "Configurant monitor d'activitat...", "it": "Configurazione monitor attività...", "de": "Aktivitätsmonitor wird eingerichtet..."},
    "Loading categories...": {"es": "Cargando categorías...", "en": "Loading categories...", "pt": "Carregando categorias...", "ca": "Carregant categories...", "it": "Caricamento categorie...", "de": "Kategorien werden geladen..."},
    "Preparing interface...": {"es": "Preparando interfaz...", "en": "Preparing interface...", "pt": "Preparando interface...", "ca": "Preparant interfície...", "it": "Preparazione interfaccia...", "de": "Benutzeroberfläche wird vorbereitet..."},
    
    # Actividad / Tareas
    "Activity Monitor": {"es": "Monitor de Actividad", "en": "Activity Monitor", "pt": "Monitor de Atividade", "ca": "Monitor d'Activitat", "it": "Monitor Attività", "de": "Aktivitätsmonitor"},
    "Total:": {"es": "Total:", "en": "Total:", "pt": "Total:", "ca": "Total:", "it": "Totale:", "de": "Gesamt:"},

    # Acerca de
    # Esta es la cadena de descripción para el diálogo "Acerca de"
    "Modern application manager for CuerdOS\nBeautiful, fast and easy to use": {
        "es": "Gestor de aplicaciones moderno para CuerdOS\nBello, rápido y fácil de usar", 
        "en": "Modern application manager for CuerdOS\nBeautiful, fast and easy to use", 
        "pt": "Gerenciador de aplicativos moderno para CuerdOS\nBonito, rápido e fácil de usar", 
        "ca": "Gestor d'aplicacions modern per a CuerdOS\nBonic, ràpid i fàcil d'utilitzar", 
        "it": "Gestore applicazioni moderno per CuerdOS\nBello, veloce e facile da usare", 
        "de": "Moderner Anwendungsmanager für CuerdOS\nSchön, schnell und einfach zu bedienen"
    },
    "CuerdOS Website": {"es": "Sitio Web de CuerdOS", "en": "CuerdOS Website", "pt": "Site da CuerdOS", "ca": "Lloc Web de CuerdOS", "it": "Sito Web di CuerdOS", "de": "CuerdOS-Website"},
    
    # Diálogo de Idioma
    "Select your preferred language:": {"es": "Seleccione su idioma preferido:", "en": "Select your preferred language:", "pt": "Selecione seu idioma preferido:", "ca": "Seleccioneu el vostre idioma preferit:", "it": "Seleziona la tua lingua preferita:", "de": "Wählen Sie Ihre bevorzugte Sprache:"},
    "Restart required": {"es": "Reinicio necesario", "en": "Restart required", "pt": "Reinicialização necessária", "ca": "Reinici necessari", "it": "Riavvio richiesto", "de": "Neustart erforderlich"},
    "The application must be restarted for the language change to take full effect.": {"es": "La aplicación debe reiniciarse para que el cambio de idioma surta efecto completo.", "en": "The application must be restarted for the language change to take full effect.", "pt": "O aplicativo deve ser reiniciado para que a mudança de idioma tenha efeito total.", "ca": "L'aplicació s'ha de reiniciar perquè el canvi d'idioma tingui efecte complet.", "it": "L'applicazione deve essere riavviata affinché il cambio de lingua abbia pieno effetto.", "de": "Die Anwendung muss neu gestartet werden, damit die Sprachumstellung vollständig wirksam wird."},
    "Close": {"es": "Cerrar", "en": "Close", "pt": "Fechar", "ca": "Tancar", "it": "Chiudi", "de": "Schließen"},
    
    # Cadenas de Estado y Acción
    "Install": {"es": "Instalar", "en": "Install", "pt": "Instalar", "ca": "Instal·lar", "it": "Installa", "de": "Installieren"},
    "Uninstall": {"es": "Desinstalar", "en": "Uninstall", "pt": "Desinstalar", "ca": "Desinstal·lar", "it": "Disinstalla", "de": "Deinstallieren"},
    "Available": {"es": "Disponible", "en": "Available", "pt": "Disponível", "ca": "Disponible", "it": "Disponibile", "de": "Verfügbar"},
    "Installed": {"es": "Instalado", "en": "Installed", "pt": "Instalado", "ca": "Instal·lat", "it": "Installato", "de": "Installiert"},
    "Installing": {"es": "Instalando", "en": "Installing", "pt": "Instalando", "ca": "Instal·lant", "it": "Installazione in corso", "de": "Wird installiert"},
    "Removing": {"es": "Desinstalando", "en": "Removing", "pt": "Removendo", "ca": "Eliminant", "it": "Rimozione in corso", "de": "Wird entfernt"},
}

class Translator:
    def __init__(self):
        # Añadir Catalán, Italiano, Alemán a los idiomas soportados
        self.supported_langs = {'es', 'en', 'pt', 'ca', 'it', 'de'}
        self.lang_map = {
            'es': 'Español', 'en': 'English', 'pt': 'Português', 
            'ca': 'Català', 'it': 'Italiano', 'de': 'Deutsch'
        }
        self.current_lang = self.load_language()

    def load_language(self):
        """Intenta cargar el idioma desde la configuración, o detecta el idioma del sistema."""
        
        # 1. Cargar desde config.json
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'language' in config and config['language'] in self.supported_langs:
                        return config['language']
            except:
                pass
                
        # 2. Detectar idioma del sistema
        try:
            # Obtiene el idioma del entorno (LC_ALL, LC_MESSAGES, LANG)
            sys_locale = locale.getlocale()[0]
            if sys_locale:
                # Normaliza a 'es', 'en', 'pt', 'ca', 'it', 'de', etc.
                lang_code = sys_locale.split('_')[0]
                if lang_code in self.supported_langs:
                    return lang_code
        except:
            pass
        
        # 3. Idioma predeterminado
        return 'es'
    
    def save_language(self, lang):
        """Guarda el nuevo idioma en el archivo de configuración."""
        if lang not in self.supported_langs:
            return False
            
        try:
            config = {}
            if CONFIG_FILE.exists():
                try:
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except:
                    pass
                    
            config['language'] = lang
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            self.current_lang = lang
            return True
        except Exception as e:
            print(f"Error saving language config: {e}")
            return False

    def gettext(self, text):
        """Obtiene la traducción para un texto dado."""
        translation = TRANSLATIONS.get(text, {})
        # Devuelve la traducción si existe, o el texto original si no se encuentra
        return translation.get(self.current_lang, text)

# Instancia global del traductor
translator_instance = Translator()
_ = translator_instance.gettext # Alias común para gettext