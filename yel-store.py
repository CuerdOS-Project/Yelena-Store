#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "yelena-store"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRANSLATIONS_CONFIG_DIR = Path.home() / '.local' / 'share' / 'yelena-store'
TRANSLATIONS_CONFIG_FILE = TRANSLATIONS_CONFIG_DIR / 'config.json'
SUPPORTED_LANGS = ["es", "en", "it", "pt", "ca", "de"]

def _get_system_language():
    """Detecta el idioma del sistema"""
    import locale
    for env_var in ['LANG', 'LC_ALL', 'LC_MESSAGES']:
        system_locale = os.environ.get(env_var)
        if system_locale and system_locale != 'C':
            break
    
    if not system_locale or system_locale == 'C':
        try:
            system_locale = locale.getlocale()[0] or locale.getdefaultlocale()[0]
        except:
            pass
    
    if system_locale and system_locale != 'C':
        try:
            lang_code = system_locale.split('_')[0].split('.')[0].lower()
            if lang_code in SUPPORTED_LANGS:
                return lang_code
        except:
            pass
    return 'es'

def _load_config():
    """Carga la configuración existente"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_to_both_configs(lang_code, auto_detect=True):
    """Guarda el idioma en ambos archivos de configuración"""
    for config_dir, config_file in [(CONFIG_DIR, CONFIG_FILE),
                                     (TRANSLATIONS_CONFIG_DIR, TRANSLATIONS_CONFIG_FILE)]:
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            config = {'language': lang_code, 'auto_detect_language': auto_detect}
            
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    existing.update(config)
                    config = existing
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando config: {e}")

# Cargar configuración
config = _load_config()
auto_detect = config.get('auto_detect_language', True)

if not auto_detect and 'language' in config:
    selected_lang = config['language']
else:
    selected_lang = _get_system_language()
    _save_to_both_configs(selected_lang, True)

# Configurar variables de entorno para el idioma
for var in ['LANGUAGE', 'LANG', 'LC_ALL']:
    os.environ[var] = f"{selected_lang}.UTF-8" if var != 'LANGUAGE' else selected_lang

# =============================================================================
# IMPORTACIONES GTK Y MÓDULOS
# =============================================================================

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk

# Configurar backend gráfico
if 'WAYLAND_DISPLAY' in os.environ:
    os.environ['GDK_BACKEND'] = 'wayland'
elif 'DISPLAY' in os.environ:
    os.environ['GDK_BACKEND'] = 'x11'

import threading
import subprocess
import time
from engine import ActivityManager, CatalogManager, Application
from store_widgets import ActivityWidget, PackageTileWidget, PackageListWidget, AppDetailDialog, LanguageDialog
from translations import _

BASE_DIR = Path(__file__).resolve().parent
STORE_ICON = BASE_DIR / 'yel-store.svg'

# =============================================================================
# VENTANA PRINCIPAL
# =============================================================================

class YelenaStoreWindow(Gtk.Window):
    """Ventana principal de Yelena Store con diseño compacto"""
    
    def __init__(self):
        super().__init__(title=_("Yelena Store"))
        
        # Tamaño optimizado para pantallas pequeñas (800x600 en lugar de 900x640)
        self.set_default_size(800, 600)
        
        # Propiedades adicionales para compatibilidad con docks y paneles
        self.set_wmclass("yel-store", "Yel-Store")
        self.set_role("yel-store-main")
        
        # Configurar iconos con compatibilidad mejorada
        self._setup_window_icons()
        
        # Estado UI
        self.widget_map = {}
        self.detail_widgets = {}
        self.navigation_history = []
        self.current_search_query = None
        self.catalog_loaded = False
        self.loading_progress_value = 0.0
        self.loading_animation_direction = 1
        
        # Managers (inicializar después para no bloquear)
        self.catalog = None
        self.activity_manager = None
        self.category_map = {}
        
        # Construir UI básica (header y stack vacío)
        self._create_basic_ui()
        
        # Mostrar mensaje de carga INMEDIATAMENTE
        self._show_loading_screen()
        
        self.connect("delete-event", self._on_delete_event)
        
        # Cargar catálogo en segundo plano
        threading.Thread(target=self._load_catalog_async, daemon=True).start()
    
    def _setup_window_icons(self):
        """Configura iconos con múltiples fallbacks para compatibilidad con COSMIC/XFCE/docklike"""
        app_name = "yel-store"
        icon_paths = [
            str(STORE_ICON) if STORE_ICON.exists() else None,
            f"{app_name}.svg",
            f"icons/{app_name}.svg",
            os.path.join(os.path.dirname(__file__), f"{app_name}.svg"),
            os.path.join(os.path.dirname(__file__), "icons", f"{app_name}.svg"),
            f"/usr/share/{app_name}/{app_name}.svg",
            "/usr/share/yelena-store/store.svg",
            f"/usr/share/icons/hicolor/scalable/apps/{app_name}.svg",
            f"/usr/share/pixmaps/{app_name}.svg",
            f"/usr/share/icons/hicolor/256x256/apps/{app_name}.png",
        ]
        
        # Filtrar None
        icon_paths = [p for p in icon_paths if p]
        
        # Intentar establecer icono desde archivo
        for icon_path in icon_paths:
            try:
                abs_path = os.path.abspath(icon_path) if not icon_path.startswith('/usr') else icon_path
                if os.path.exists(abs_path):
                    self.set_icon_from_file(abs_path)
                    break
            except Exception:
                pass
        
        # Establecer nombre de icono para que los temas lo encuentren
        try:
            self.set_icon_name(app_name)
        except:
            pass
        
        # Cargar iconos en múltiples tamaños para mejor compatibilidad
        try:
            icon_theme = Gtk.IconTheme.get_default()
            icon_list = []
            
            for size in [16, 22, 24, 32, 48, 64, 128, 256]:
                try:
                    pixbuf = icon_theme.load_icon(app_name, size, 
                                                  Gtk.IconLookupFlags.FORCE_SIZE)
                    if pixbuf:
                        icon_list.append(pixbuf)
                except:
                    for icon_path in icon_paths:
                        try:
                            abs_path = os.path.abspath(icon_path) if not icon_path.startswith('/usr') else icon_path
                            if os.path.exists(abs_path):
                                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(abs_path, size, size)
                                icon_list.append(pixbuf)
                                break
                        except:
                            continue
            
            if icon_list:
                self.set_icon_list(icon_list)
        except Exception:
            pass
    
    def _show_loading_screen(self):
        """Muestra una pantalla de carga mientras se inicializa el catálogo"""
        # Crear un contenedor para la pantalla de carga
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=30)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)
        
        # Logo/Nombre grande de Yelena Store con estilo
        store_name_label = Gtk.Label()
        store_name_label.set_markup(
            "<span size='xx-large' weight='bold' foreground='#3498db'>YELENA</span> "
            "<span size='xx-large' weight='bold' foreground='#2ecc71'>STORE</span>"
        )
        loading_box.pack_start(store_name_label, False, False, 0)
        
        # Subtítulo
        subtitle_label = Gtk.Label()
        subtitle_label.set_markup("<span size='medium' foreground='#7f8c8d'>{}</span>".format(_('Application Manager')))
        loading_box.pack_start(subtitle_label, False, False, 0)
        
        # Separador visual
        separator_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        separator_box.set_halign(Gtk.Align.CENTER)
        separator_box.set_size_request(200, 3)
        separator_box.get_style_context().add_class("separator")
        
        # Agregar CSS para el separador con gradiente
        css_provider = Gtk.CssProvider()
        css_data = """
        .separator {
            background-image: linear-gradient(to right, #3498db, #2ecc71);
            border-radius: 2px;
        }
        """
        css_provider.load_from_data(css_data.encode())
        separator_box.get_style_context().add_provider(
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        loading_box.pack_start(separator_box, False, False, 15)
        
        # Spinner animado más grande
        spinner = Gtk.Spinner()
        spinner.set_size_request(80, 80)
        spinner.start()
        loading_box.pack_start(spinner, False, False, 10)
        
        # Mensaje de carga con animación
        self.loading_message_label = Gtk.Label()
        self.loading_message_label.set_markup(
            f"<span size='large' weight='bold'>{_('Loading catalog...')}</span>"
        )
        loading_box.pack_start(self.loading_message_label, False, False, 0)
        
        # Submensaje
        sub_label = Gtk.Label()
        sub_label.set_markup(
            f"<span size='small' foreground='#95a5a6'>{_('Please wait while we prepare everything')}</span>"
        )
        loading_box.pack_start(sub_label, False, False, 0)
        
        # Barra de progreso estilo "indeterminado"
        self.loading_progress = Gtk.ProgressBar()
        self.loading_progress.set_size_request(300, 6)
        self.loading_progress.set_show_text(False)
        loading_box.pack_start(self.loading_progress, False, False, 15)
        
        # Agregar la pantalla de carga al stack
        self.stack.add_named(loading_box, "loading")
        self.stack.set_visible_child_name("loading")
        
        # Forzar que se muestre todo inmediatamente
        self.show_all()
        
        # Iniciar animación de la barra de progreso
        self._start_loading_animation()

    
    def _start_loading_animation(self):
        """Inicia la animación de la barra de progreso"""
        self.loading_progress_value = 0.0
        self.loading_animation_direction = 1
        
        def animate():
            if not self.catalog_loaded:
                # Animar la barra de progreso de ida y vuelta
                self.loading_progress_value += 0.02 * self.loading_animation_direction
                
                if self.loading_progress_value >= 1.0:
                    self.loading_animation_direction = -1
                elif self.loading_progress_value <= 0.0:
                    self.loading_animation_direction = 1
                
                self.loading_progress.set_fraction(self.loading_progress_value)
                return True  # Continuar animación
            else:
                # Completar la barra cuando termine la carga
                self.loading_progress.set_fraction(1.0)
                return False  # Detener animación
        
        # Ejecutar animación cada 50ms
        GLib.timeout_add(50, animate)
    
    def _load_catalog_async(self):
        """Carga el catálogo en segundo plano (no bloquea la UI)"""
        try:
            print("[LOADING] Iniciando carga de catálogo en segundo plano...")
            
            # Actualizar mensaje de carga
            GLib.idle_add(self._update_loading_message, _("Initializing managers..."))
            
            # 1. Inicializar managers (esto puede ser lento)
            print("[LOADING] Inicializando CatalogManager...")
            import time
            start_time = time.time()
            
            self.catalog = CatalogManager()
            elapsed = time.time() - start_time
            print(f"[LOADING] CatalogManager inicializado en {elapsed:.2f}s")
            
            GLib.idle_add(self._update_loading_message, _("Setting up activity monitor..."))
            
            print("[LOADING] Inicializando ActivityManager...")
            start_time = time.time()
            self.activity_manager = ActivityManager(parent_window=self)
            elapsed = time.time() - start_time
            print(f"[LOADING] ActivityManager inicializado en {elapsed:.2f}s")
            
            # 2. Configurar hooks
            GLib.idle_add(self.catalog.set_gui_hooks, self)
            GLib.idle_add(self.activity_manager.set_gui_hooks, self)
            
            GLib.idle_add(self._update_loading_message, _("Loading categories..."))
            
            # 3. Cargar categorías desde el catálogo ya inicializado
            print("[LOADING] Obteniendo categorías...")
            categories = self.catalog.get_categories()
            
            if categories:
                # Obtener idioma actual
                try:
                    from translations import translator_instance
                    current_lang = translator_instance.current_lang
                except:
                    current_lang = 'en'
                
                for cat in categories:
                    cat_id = cat.get('id', '')
                    cat_name = cat.get('name', {})
                    cat_icon = cat.get('icon', 'applications-other')
                    
                    # Obtener nombre traducido
                    if isinstance(cat_name, dict):
                        display_name = cat_name.get(current_lang, cat_name.get('en', cat_id))
                    else:
                        display_name = cat_name
                    
                    self.category_map[cat_id] = (display_name, cat_icon)
            else:
                # Categorías predeterminadas si no hay JSON
                self.category_map = {
                    "Development": (_("Development"), "applications-engineering"),
                    "Multimedia": (_("Multimedia"), "multimedia-volume-control"),
                    "Games": (_("Games"), "applications-games"),
                    "Office": (_("Office"), "x-office-document"),
                    "Internet": (_("Internet"), "network-wireless"),
                    "Graphics": (_("Graphics"), "applications-graphics"),
                    "Utilities": (_("Utilities"), "applications-accessories"),
                    "System": (_("System"), "applications-system")
                }
            
            print(f"[LOADING] Categorías listas: {len(self.category_map)}")
            
            GLib.idle_add(self._update_loading_message, _("Preparing interface..."))
            
            # 4. Marcar como cargado y actualizar UI INMEDIATAMENTE
            self.catalog_loaded = True
            print("[LOADING] ✓ Managers listos, mostrando interfaz...")
            
            # Pequeña pausa para que el mensaje se vea
            time.sleep(0.2)
            
            GLib.idle_add(self._finish_loading)
            
        except Exception as e:
            print(f"[ERROR] Error cargando catálogo: {e}")
            import traceback
            traceback.print_exc()
            GLib.idle_add(self._show_error_loading, str(e))
    
    def _update_loading_message(self, message):
        """Actualiza el mensaje de la pantalla de carga"""
        try:
            if hasattr(self, 'loading_message_label'):
                self.loading_message_label.set_markup(
                    f"<span size='large' weight='bold'>{message}</span>"
                )
        except:
            pass
        return False
    
    def _finish_loading(self):
        """Finaliza la carga y muestra las aplicaciones"""
        try:
            print("[LOADING] Finalizando carga en UI thread...")
            
            # Verificar que tenemos datos necesarios
            if not self.category_map:
                print("[ERROR] category_map está vacío!")
                self._show_error_loading("No se pudieron cargar las categorías")
                return
            
            if not self.catalog:
                print("[ERROR] catalog no está inicializado!")
                self._show_error_loading("No se pudo inicializar el catálogo")
                return
            
            # CREAR PÁGINAS PROGRESIVAMENTE para no bloquear la UI
            print("[LOADING] Creando página Home...")
            try:
                self._create_home_page()
                print("[LOADING] ✓ Página Home creada")
            except Exception as e:
                print(f"[ERROR] Error creando Home: {e}")
                import traceback
                traceback.print_exc()
                self._show_error_loading(f"Error al crear interfaz: {e}")
                return
            
            print("[LOADING] Creando página de búsqueda...")
            try:
                self._create_search_page()
                print("[LOADING] ✓ Página búsqueda creada")
            except Exception as e:
                print(f"[ERROR] Error creando búsqueda: {e}")
                # Continuar aunque falle la búsqueda
            
            # Verificar que la página Home existe
            home_page = self.stack.get_child_by_name("Home")
            if not home_page:
                print("[ERROR] ¡La página Home no se creó correctamente!")
                self._show_error_loading("Error al crear la página principal")
                return
            
            print("[LOADING] Cambiando a página Home...")
            
            # CRÍTICO: Remover la pantalla de carga del stack
            loading_page = self.stack.get_child_by_name("loading")
            if loading_page:
                print("[LOADING] Removiendo pantalla de carga...")
                self.stack.remove(loading_page)
            
            # Cambiar a Home
            self.stack.set_visible_child_name("Home")
            self.show_all()
            
            print("[LOADING] ✓ Pantalla Home ahora visible")
            
            # Cargar primeras apps rápidamente (batch pequeño)
            print("[LOADING] Cargando aplicaciones iniciales...")
            apps_loaded = 0
            try:
                if self.catalog.popular_apps and len(self.catalog.popular_apps) > 0:
                    # Cargar máximo 6 apps iniciales
                    num_apps = min(6, len(self.catalog.popular_apps))
                    for app in self.catalog.popular_apps[:num_apps]:
                        try:
                            self.generic_flowbox.add(
                                PackageTileWidget(app, self.catalog, self, self.activity_manager)
                            )
                            apps_loaded += 1
                        except Exception as e:
                            print(f"[ERROR] Error cargando app {app.name}: {e}")
                    print(f"[LOADING] ✓ {apps_loaded} aplicaciones cargadas")
                else:
                    print("[WARNING] No hay aplicaciones populares disponibles")
            except Exception as e:
                print(f"[ERROR] Error cargando apps iniciales: {e}")
                import traceback
                traceback.print_exc()
            
            self.show_all()
            
            # Programar la carga del resto en background con prioridad baja
            if self.catalog.popular_apps and len(self.catalog.popular_apps) > 6:
                GLib.idle_add(self._load_more_apps, priority=GLib.PRIORITY_LOW)
            
            GLib.idle_add(self._create_remaining_pages, priority=GLib.PRIORITY_LOW)
            
            print("[LOADING] ✓ Interfaz principal lista y visible")
            
        except Exception as e:
            print(f"[ERROR] Error fatal finalizando carga: {e}")
            import traceback
            traceback.print_exc()
            self._show_error_loading(f"Error fatal: {e}")
    
    def _load_more_apps(self):
        """Carga más aplicaciones en segundo plano"""
        try:
            # Inicializar contador si no existe
            if not hasattr(self, '_apps_loaded_count'):
                self._apps_loaded_count = 6  # Ya cargamos 6 inicialmente
                print("[LOADING] Cargando más aplicaciones Home...")
            
            # Cargar el resto de apps populares (7-20)
            if self.catalog.popular_apps and len(self.catalog.popular_apps) > self._apps_loaded_count:
                # Cargar siguiente lote de 3 apps
                end_index = min(self._apps_loaded_count + 3, len(self.catalog.popular_apps), 20)
                
                for app in self.catalog.popular_apps[self._apps_loaded_count:end_index]:
                    try:
                        self.generic_flowbox.add(
                            PackageTileWidget(app, self.catalog, self, self.activity_manager)
                        )
                        self._apps_loaded_count += 1
                    except Exception as e:
                        print(f"[ERROR] Error cargando app: {e}")
                
                self.show_all()
                
                # Si aún hay más apps por cargar, continuar
                if self._apps_loaded_count < min(len(self.catalog.popular_apps), 20):
                    return True  # Continuar en siguiente idle
            
            # Terminado
            print(f"[LOADING] ✓ Total apps Home cargadas: {self._apps_loaded_count}")
            
        except Exception as e:
            print(f"[ERROR] Error cargando más apps: {e}")
            import traceback
            traceback.print_exc()
        
        return False  # No repetir
    
    def _create_remaining_pages(self):
        """Crea las páginas restantes en segundo plano sin bloquear"""
        try:
            print("[LOADING] Creando páginas de categorías...")
            self._create_category_pages()
            
            print("[LOADING] Creando páginas adicionales...")
            self._create_tasks_page()
            self._create_details_page()
            
            # Programar carga de apps en categorías con prioridad aún más baja
            GLib.idle_add(self._load_category_apps, priority=GLib.PRIORITY_LOW)
            
            print("[LOADING] ✓ Páginas adicionales creadas")
            
        except Exception as e:
            print(f"[ERROR] Error creando páginas restantes: {e}")
            import traceback
            traceback.print_exc()
        
        return False  # No repetir
    
    def _load_category_apps(self):
        """Carga apps en categorías de forma perezosa"""
        try:
            print("[LOADING] Cargando apps en categorías...")
            
            # Cargar apps en categorías (esto puede ser lento)
            for category_id in self.category_map.keys():
                category_apps = self.catalog.get_category_packages(category_id)
                if category_apps and category_id in self.widget_map:
                    for app in category_apps:
                        self.widget_map[category_id].add(
                            PackageTileWidget(app, self.catalog, self, self.activity_manager)
                        )
            
            self.show_all()
            print("[LOADING] ✓ Todas las páginas completamente cargadas")
            
        except Exception as e:
            print(f"[ERROR] Error cargando apps de categorías: {e}")
        
        return False  # No repetir
    
    def _show_error_loading(self, error_msg):
        """Muestra un error si falla la carga del catálogo"""
        error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        error_box.set_valign(Gtk.Align.CENTER)
        error_box.set_halign(Gtk.Align.CENTER)
        
        # Icono de error
        error_icon = Gtk.Image.new_from_icon_name("dialog-error", Gtk.IconSize.DIALOG)
        error_box.pack_start(error_icon, False, False, 0)
        
        # Mensaje de error
        error_label = Gtk.Label()
        error_label.set_markup(f"<span size='x-large' weight='bold'>{_('Error loading catalog')}</span>")
        error_box.pack_start(error_label, False, False, 0)
        
        # Detalles del error
        details_label = Gtk.Label()
        details_label.set_markup(f"<span size='small' foreground='#666666'>{error_msg}</span>")
        details_label.set_line_wrap(True)
        details_label.set_max_width_chars(50)
        error_box.pack_start(details_label, False, False, 0)
        
        # Botón de reintentar
        retry_button = Gtk.Button(label=_("Retry"))
        retry_button.connect("clicked", lambda b: self._retry_loading())
        error_box.pack_start(retry_button, False, False, 10)
        
        # Reemplazar pantalla de carga con error
        loading_page = self.stack.get_child_by_name("loading")
        if loading_page:
            self.stack.remove(loading_page)
        
        self.stack.add_named(error_box, "error")
        self.stack.set_visible_child_name("error")
        self.show_all()
    
    def _retry_loading(self):
        """Reintenta cargar el catálogo"""
        # Remover pantalla de error
        error_page = self.stack.get_child_by_name("error")
        if error_page:
            self.stack.remove(error_page)
        
        # Mostrar pantalla de carga nuevamente
        self._show_loading_screen()
        
        # Reintentar carga en segundo plano
        threading.Thread(target=self._load_catalog_async, daemon=True).start()
    
    def _load_apps(self):
        """Carga aplicaciones del catálogo"""
        # Cargar flatpaks populares desde flatpaks.json para la página Home
        if self.catalog.popular_apps:
            # Cargar en Home (primeras 20 flatpaks populares)
            for app in self.catalog.popular_apps[:20]:
                self.generic_flowbox.add(
                    PackageTileWidget(app, self.catalog, self, self.activity_manager)
                )
        
        # Cargar paquetes APT desde catalog.json para cada categoría
        for category_id in self.category_map.keys():
            category_apps = self.catalog.get_category_packages(category_id)
            if category_apps and category_id in self.widget_map:
                for app in category_apps:
                    self.widget_map[category_id].add(
                        PackageTileWidget(app, self.catalog, self, self.activity_manager)
                    )
        
        self.show_all()
        self.stack.set_visible_child_name("Home")
    
    def _create_basic_ui(self):
        """Crea la interfaz de usuario básica (header como toolbar y stack vacío)"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)
        
        # Header bar como toolbar (NO como titlebar)
        header = self._create_header()
        main_box.pack_start(header, False, False, 0)
        
        # Stack para las diferentes vistas (inicialmente vacío)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)  # Más rápido para pantallas pequeñas
        
        main_box.pack_start(self.stack, True, True, 0)
        
        # Statusbar compacto
        self.statusbar = Gtk.Statusbar()
        self.status_context = self.statusbar.get_context_id("main")
        self.statusbar.push(self.status_context, _("Ready"))
        main_box.pack_end(self.statusbar, False, False, 0)
    
    def _create_header(self):
        """Crea la barra de herramientas (HeaderBar como toolbar, NO como titlebar)"""
        # IMPORTANTE: HeaderBar se usa como barra de herramientas, NO como titlebar
        # La ventana tendrá barra de título tradicional del sistema
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)  # No mostrar botones de ventana
        # NO llamar a self.set_titlebar(header) - esto la hace titlebar
        
        # Botón atrás
        self.back_btn = Gtk.Button()
        self.back_btn.set_image(Gtk.Image.new_from_icon_name(
            "go-previous-symbolic", Gtk.IconSize.BUTTON
        ))
        self.back_btn.set_tooltip_text(_("Back"))
        self.back_btn.connect("clicked", self.go_back)
        self.back_btn.set_no_show_all(True)
        header.pack_start(self.back_btn)
        
        # Botón home
        self.home_btn = Gtk.Button()
        self.home_btn.set_image(Gtk.Image.new_from_icon_name(
            "go-home-symbolic", Gtk.IconSize.BUTTON
        ))
        self.home_btn.set_tooltip_text(_("Home"))
        self.home_btn.connect("clicked", self.go_home)
        self.home_btn.set_no_show_all(True)
        header.pack_start(self.home_btn)
        
        # Barra de búsqueda compacta
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search applications..."))
        self.search_entry.set_width_chars(25)  # Más corta para pantallas pequeñas
        self.search_entry.connect("activate", lambda e: self.search_packages())
        header.set_custom_title(self.search_entry)
        
        # Botón de tareas
        self.tasks_btn = Gtk.Button()
        self.tasks_btn.set_image(Gtk.Image.new_from_icon_name(
            "emblem-downloads-symbolic", Gtk.IconSize.BUTTON
        ))
        self.tasks_btn.set_tooltip_text(_("Tasks"))
        self.tasks_btn.connect("clicked", lambda b: self._navigate_to("Tasks"))
        header.pack_end(self.tasks_btn)
        
        # Menú
        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name(
            "open-menu-symbolic", Gtk.IconSize.BUTTON
        ))
        
        menu = Gtk.Menu()
        
        # Opción de actualizaciones
        updates_item = Gtk.MenuItem(label=_("Updates"))
        updates_item.connect("activate", self._open_updates_manager)
        menu.append(updates_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Opción de idioma
        lang_item = Gtk.MenuItem(label=_("Change Language"))
        lang_item.connect("activate", self._show_language_dialog)
        menu.append(lang_item)
        
        # Opción de acerca de
        about_item = Gtk.MenuItem(label=_("About"))
        about_item.connect("activate", self._show_about)
        menu.append(about_item)
        
        menu.show_all()
        menu_btn.set_popup(menu)
        header.pack_end(menu_btn)
        
        return header
    
    def _create_pages(self):
        """Crea las diferentes páginas de la aplicación"""
        # Página Home
        self._create_home_page()
        
        # Páginas de categorías
        self._create_category_pages()
        
        # Página de búsqueda
        self._create_search_page()
        
        # Página de tareas
        self._create_tasks_page()
        
        # Página de detalles
        self._create_details_page()
    
    def _create_home_page(self):
        """Crea la página de inicio"""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        
        # Sección de categorías (sin título grande)
        categories_label = Gtk.Label()
        categories_label.set_markup(f"<span size='medium'><b>{_('Categories')}</b></span>")
        categories_label.set_halign(Gtk.Align.START)
        main_box.pack_start(categories_label, False, False, 0)
        
        # Grid de categorías responsive (ahora usando FlowBox para adaptabilidad)
        categories_flowbox = Gtk.FlowBox()
        categories_flowbox.set_valign(Gtk.Align.START)
        categories_flowbox.set_max_children_per_line(3)  # Máximo 3 columnas
        categories_flowbox.set_min_children_per_line(2)  # Mínimo 2 columnas
        categories_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        categories_flowbox.set_column_spacing(8)
        categories_flowbox.set_row_spacing(8)
        categories_flowbox.set_homogeneous(True)
        
        # Colores para las categorías
        category_colors = {
            "Development": "#3498db",    # Azul
            "Multimedia": "#e74c3c",     # Rojo
            "Games": "#9b59b6",          # Púrpura
            "Office": "#2ecc71",         # Verde
            "Internet": "#f39c12",       # Naranja
            "Graphics": "#1abc9c",       # Turquesa
            "Utilities": "#34495e",      # Gris oscuro
            "System": "#e67e22",         # Naranja oscuro
        }
        
        # Añadir botones de categoría
        for category_id, (category_name, icon_name) in self.category_map.items():
            # Frame con color
            cat_frame = Gtk.Frame()
            cat_frame.set_shadow_type(Gtk.ShadowType.OUT)
            
            cat_button = Gtk.Button()
            cat_button.set_relief(Gtk.ReliefStyle.NONE)
            cat_button.set_size_request(220, 65)
            
            # Aplicar color de fondo usando CSS
            color = category_colors.get(category_id, "#7f8c8d")
            css_provider = Gtk.CssProvider()
            css_data = f"""
            button {{
                background-image: linear-gradient(to bottom, {color}, {self._darken_color(color)});
                background-size: 100% 100%;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }}
            button:hover {{
                background-image: linear-gradient(to bottom, {self._lighten_color(color)}, {color});
            }}
            """
            css_provider.load_from_data(css_data.encode())
            cat_button.get_style_context().add_provider(
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            
            cat_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            cat_box.set_margin_top(10)
            cat_box.set_margin_bottom(10)
            cat_box.set_margin_start(12)
            cat_box.set_margin_end(12)
            
            cat_icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            cat_label = Gtk.Label()
            cat_label.set_markup(f"<span size='medium' foreground='white'><b>{category_name}</b></span>")
            
            cat_box.pack_start(cat_icon, False, False, 0)
            cat_box.pack_start(cat_label, True, False, 0)
            
            cat_button.add(cat_box)
            cat_button.connect("clicked", lambda w, cid: self._navigate_to(f"Category_{cid}"), category_id)
            
            cat_frame.add(cat_button)
            categories_flowbox.add(cat_frame)
        
        main_box.pack_start(categories_flowbox, False, False, 0)
        
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        # Sección de aplicaciones Flatpak
        popular_label = Gtk.Label()
        popular_label.set_markup(f"<span size='medium'><b>{_('Flatpak Applications')}</b></span>")
        popular_label.set_halign(Gtk.Align.START)
        main_box.pack_start(popular_label, False, False, 0)
        
        # Grid de aplicaciones (más compacto)
        self.generic_flowbox = Gtk.FlowBox()
        self.generic_flowbox.set_valign(Gtk.Align.START)
        self.generic_flowbox.set_max_children_per_line(5)  # Ajustado para pantallas pequeñas
        self.generic_flowbox.set_min_children_per_line(3)
        self.generic_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.generic_flowbox.set_column_spacing(8)
        self.generic_flowbox.set_row_spacing(8)
        
        main_box.pack_start(self.generic_flowbox, True, True, 0)
        
        scrolled.add(main_box)
        self.stack.add_named(scrolled, "Home")
    
    def _lighten_color(self, hex_color):
        """Aclara un color hexadecimal"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = min(255, int(r * 1.2))
        g = min(255, int(g * 1.2))
        b = min(255, int(b * 1.2))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _darken_color(self, hex_color):
        """Oscurece un color hexadecimal"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = int(r * 0.8)
        g = int(g * 0.8)
        b = int(b * 0.8)
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _create_category_pages(self):
        """Crea las páginas de categorías"""
        for category_id, (category_name, icon_name) in self.category_map.items():
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.set_margin_top(12)
            box.set_margin_bottom(12)
            box.set_margin_start(12)
            box.set_margin_end(12)
            
            # Header de categoría
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            title = Gtk.Label()
            title.set_markup(f"<span size='large'><b>{category_name}</b></span>")
            title.set_halign(Gtk.Align.START)
            
            header_box.pack_start(icon, False, False, 0)
            header_box.pack_start(title, False, False, 0)
            
            box.pack_start(header_box, False, False, 0)
            box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
            
            # FlowBox para aplicaciones
            flowbox = Gtk.FlowBox()
            flowbox.set_valign(Gtk.Align.START)
            flowbox.set_max_children_per_line(5)
            flowbox.set_min_children_per_line(3)
            flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
            flowbox.set_column_spacing(8)
            flowbox.set_row_spacing(8)
            
            self.widget_map[category_id] = flowbox
            
            box.pack_start(flowbox, True, True, 0)
            scrolled.add(box)
            
            self.stack.add_named(scrolled, f"Category_{category_id}")
    
    def _create_search_page(self):
        """Crea la página de búsqueda"""
        self.search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Contenedor de búsqueda con barra de progreso
        self.search_spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.search_spinner_box.set_valign(Gtk.Align.CENTER)
        self.search_spinner_box.set_halign(Gtk.Align.CENTER)
        
        # Icono de lupa grande
        search_icon = Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.DIALOG)
        search_icon.set_pixel_size(96)
        search_icon.set_opacity(0.3)
        
        # Spinner animado (pequeño, decorativo)
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        
        # Etiquetas de estado
        self.search_status_label = Gtk.Label()
        self.search_status_label.set_markup(f"<span size='large'><b>{_('Searching packages...')}</b></span>")
        self.search_status_label.set_justify(Gtk.Justification.CENTER)
        
        self.search_detail_label = Gtk.Label()
        self.search_detail_label.set_markup(f"<span size='medium'>{_('This may take a few seconds')}</span>")
        self.search_detail_label.set_justify(Gtk.Justification.CENTER)
        self.search_detail_label.get_style_context().add_class("dim-label")
        
        # BARRA DE PROGRESO
        self.search_progress_bar = Gtk.ProgressBar()
        self.search_progress_bar.set_size_request(400, 10)
        self.search_progress_bar.set_show_text(False)
        self.search_progress_bar.set_fraction(0.0)
        
        # Label de porcentaje
        self.search_progress_label = Gtk.Label()
        self.search_progress_label.set_markup("<span size='small'>0%</span>")
        self.search_progress_label.get_style_context().add_class("dim-label")
        
        self.search_spinner_box.pack_start(search_icon, False, False, 0)
        self.search_spinner_box.pack_start(spinner, False, False, 0)
        self.search_spinner_box.pack_start(self.search_status_label, False, False, 0)
        self.search_spinner_box.pack_start(self.search_detail_label, False, False, 0)
        self.search_spinner_box.pack_start(self.search_progress_bar, False, False, 10)
        self.search_spinner_box.pack_start(self.search_progress_label, False, False, 0)
        self.search_spinner_box.set_no_show_all(True)
        
        # Container de resultados
        self.search_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.search_container.set_margin_top(12)
        self.search_container.set_margin_bottom(12)
        self.search_container.set_margin_start(12)
        self.search_container.set_margin_end(12)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.search_container)
        
        self.search_box.pack_start(self.search_spinner_box, True, True, 0)
        self.search_box.pack_start(scrolled, True, True, 0)
        
        self.stack.add_named(self.search_box, "Search")
    
    def _create_tasks_page(self):
        """Crea la página de tareas"""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        icon = Gtk.Image.new_from_icon_name("emblem-downloads", Gtk.IconSize.LARGE_TOOLBAR)
        title = Gtk.Label()
        title.set_markup(f"<span size='large'><b>{_('Activity Monitor')}</b></span>")
        title.set_halign(Gtk.Align.START)
        
        header_box.pack_start(icon, False, False, 0)
        header_box.pack_start(title, False, False, 0)
        
        box.pack_start(header_box, False, False, 0)
        
        # Contador
        self.activity_total_label = Gtk.Label()
        self.activity_total_label.set_markup(f"<b>{_('Total:')}</b> 0")
        self.activity_total_label.set_halign(Gtk.Align.START)
        box.pack_start(self.activity_total_label, False, False, 0)
        
        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        # Container de actividades
        self.activities_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(self.activities_container, True, True, 0)
        
        scrolled.add(box)
        self.stack.add_named(scrolled, "Tasks")
    
    def _create_details_page(self):
        """Crea la página de detalles"""
        self.details_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack.add_named(self.details_container, "Details")
    
    def _navigate_to(self, page_name):
        """Navega a una página específica"""
        current_page = self.stack.get_visible_child_name()
        
        if current_page != page_name:
            self.navigation_history.append(current_page)
            self.stack.set_visible_child_name(page_name)
            
            # Actualizar botones de navegación
            if len(self.navigation_history) > 0:
                self.back_btn.show()
                self.home_btn.show()
            else:
                self.back_btn.hide()
                self.home_btn.hide()
    
    def go_back(self, btn):
        """Vuelve a la página anterior"""
        if self.navigation_history:
            previous_page = self.navigation_history.pop()
            self.stack.set_visible_child_name(previous_page)
            
            if len(self.navigation_history) == 0:
                self.back_btn.hide()
                self.home_btn.hide()
    
    def go_home(self, btn):
        """Vuelve a la página de inicio"""
        self.navigation_history.clear()
        self.stack.set_visible_child_name("Home")
        self.back_btn.hide()
        self.home_btn.hide()
    
    def search_packages(self):
        """Busca paquetes con barra de progreso"""
        query = self.search_entry.get_text().strip()
        
        if not query or len(query) < 2:
            return
        
        # Verificar si el catálogo está cargado
        if not self.catalog_loaded or not self.catalog:
            self.statusbar.push(self.status_context, _("Catalog is still loading, please wait..."))
            return
        
        self.current_search_query = query
        self._navigate_to("Search")
        
        # Limpiar completamente resultados anteriores
        for child in self.search_container.get_children():
            self.search_container.remove(child)
            child.destroy()
        
        # Mostrar spinner y resetear progreso
        self.search_progress_bar.set_fraction(0.0)
        self.search_progress_label.set_markup("<span size='small'>0%</span>")
        self.search_spinner_box.show()
        
        # Limpiar estado en statusbar
        self.statusbar.pop(self.status_context)
        self.statusbar.push(self.status_context, f"{_('Searching')} '{query}'...")
        
        def search_worker():
            results = []
            
            # ===== FASE 0: Inicializando (0-10%) =====
            GLib.idle_add(self._update_search_progress, 0.05, 
                         _('Searching packages...'),
                         _('Initializing search...'))
            
            # ===== FASE 1: Buscar en catálogo local (10-30%) =====
            GLib.idle_add(self._update_search_progress, 0.15,
                         _('Searching packages...'),
                         _('Searching in catalog...'))
            
            catalog_results = []
            if self.catalog and self.catalog.popular_apps:
                query_lower = query.lower()
                for app in self.catalog.popular_apps:
                    if (query_lower in app.name.lower() or 
                        query_lower in app.summary.lower() or
                        query_lower in app.app_id.lower()):
                        catalog_results.append(app)
            
            GLib.idle_add(self._update_search_progress, 0.30,
                         _('Searching packages...'),
                         _('Catalog search complete'))
            
            # Mostrar progreso del catálogo
            if catalog_results:
                GLib.idle_add(self._display_partial_results, query, catalog_results, 
                            f"{_('Results from catalog')}")
            
            # ===== FASE 2: Buscar en APT (30-60%) =====
            apt_results = []
            if self.catalog and self.catalog.apt_manager.is_available():
                GLib.idle_add(self._update_search_progress, 0.40,
                             _('Searching packages...'),
                             _('Searching in APT repositories...'))
                try:
                    apt_results = self.catalog.apt_manager.search(query)
                    GLib.idle_add(self._update_search_progress, 0.60,
                                 _('Searching packages...'),
                                 _('APT search complete'))
                except Exception as e:
                    print(f"[SEARCH] Error en búsqueda APT: {e}")
            
            # ===== FASE 3: Buscar en Flatpak (60-85%) =====
            flatpak_results = []
            if self.catalog and self.catalog.flatpak_manager.is_available():
                GLib.idle_add(self._update_search_progress, 0.70,
                             _('Searching packages...'),
                             _('Searching in Flatpak repositories...'))
                try:
                    flatpak_results = self.catalog.flatpak_manager.search(query)
                    GLib.idle_add(self._update_search_progress, 0.85,
                                 _('Searching packages...'),
                                 _('Flatpak search complete'))
                except Exception as e:
                    print(f"[SEARCH] Error en búsqueda Flatpak: {e}")
            
            # ===== FASE 4: Procesando resultados (85-100%) =====
            GLib.idle_add(self._update_search_progress, 0.90,
                         _('Searching packages...'),
                         _('Processing results...'))
            
            # Combinar resultados evitando duplicados
            repo_results = apt_results + flatpak_results
            seen_ids = {app.app_id for app in catalog_results}
            for app in repo_results:
                if app.app_id not in seen_ids:
                    results.append(app)
                    seen_ids.add(app.app_id)
            
            # Catálogo primero, luego repositorios
            results = catalog_results + results
            
            GLib.idle_add(self._update_search_progress, 1.0,
                         _('Search complete!'),
                         f"{len(results)} {_('packages found')}")
            
            # Pequeña pausa para mostrar el 100% antes de mostrar resultados
            time.sleep(0.3)
            
            # Mostrar resultados finales
            GLib.idle_add(self._display_search_results, query, results)
        
        threading.Thread(target=search_worker, daemon=True).start()
    
    def _update_search_progress(self, fraction, main_text, detail_text):
        """Actualiza la barra de progreso y los mensajes"""
        self.search_progress_bar.set_fraction(fraction)
        percentage = int(fraction * 100)
        self.search_progress_label.set_markup(f"<span size='small'>{percentage}%</span>")
        self.search_status_label.set_markup(f"<span size='large'><b>{main_text}</b></span>")
        self.search_detail_label.set_markup(f"<span size='medium'>{detail_text}</span>")
        self.statusbar.pop(self.status_context)
        self.statusbar.push(self.status_context, f"{main_text} - {detail_text}")
        return False
    
    def _display_partial_results(self, query, results, section_title):
        """Muestra resultados parciales durante la búsqueda - SIMPLIFICADO"""
        # NO mostrar resultados parciales para evitar bugs en la GUI
        # Solo actualizar el contador en la statusbar
        self.statusbar.pop(self.status_context)
        self.statusbar.push(self.status_context, 
                           f"{section_title}: {len(results)} {_('found')}")
        return False
    
    def _display_search_results(self, query, results):
        """Muestra los resultados de búsqueda progresivamente"""
        self.search_spinner_box.hide()
        
        # Limpiar completamente
        for child in self.search_container.get_children():
            self.search_container.remove(child)
            child.destroy()
        
        if not results:
            self._show_no_results(query)
            # LIMPIEZA AGRESIVA después de búsqueda vacía
            self._aggressive_cleanup_after_search()
            return
        
        # Header
        header_label = Gtk.Label()
        header_label.set_markup(
            f"<span size='large'><b>{len(results)}</b> {_('results for')} <i>'{query}'</i></span>"
        )
        header_label.set_halign(Gtk.Align.START)
        header_label.set_margin_bottom(8)
        self.search_container.pack_start(header_label, False, False, 0)
        
        self.search_container.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )
        
        # Lista de resultados
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.search_container.pack_start(listbox, True, True, 0)
        
        # Mostrar el contenedor primero
        self.show_all()
        
        # Agregar resultados PROGRESIVAMENTE para no bloquear la GUI
        self._add_results_progressively(listbox, results, 0)
        
        # Actualizar statusbar
        self.statusbar.pop(self.status_context)
        self.statusbar.push(self.status_context, f"{_('Loading')} {len(results)} {_('results')}...")
        
        return False
    
    def _add_results_progressively(self, listbox, results, index):
        """Agrega resultados progresivamente sin bloquear la GUI"""
        BATCH_SIZE = 5  # Agregar 5 paquetes a la vez
        MAX_PER_BATCH = 5
        
        # Calcular cuántos paquetes agregar en esta iteración
        end_index = min(index + BATCH_SIZE, len(results))
        
        # Agregar el siguiente lote de paquetes
        for i in range(index, end_index):
            app = results[i]
            try:
                row = PackageListWidget(app, self.catalog, self, self.activity_manager)
                listbox.add(row)
            except Exception as e:
                print(f"[SEARCH] Error agregando paquete {app.name}: {e}")
        
        # Mostrar los widgets agregados
        listbox.show_all()
        
        # Actualizar barra de estado con progreso
        progress = int((end_index / len(results)) * 100)
        self.statusbar.pop(self.status_context)
        self.statusbar.push(self.status_context, 
                           f"{_('Loading results')}: {end_index}/{len(results)} ({progress}%)")
        
        # Si quedan más resultados, programar la siguiente iteración
        if end_index < len(results):
            # Continuar después de 50ms (permite que la GUI se actualice)
            GLib.timeout_add(50, self._add_results_progressively, listbox, results, end_index)
        else:
            # Todos los resultados agregados
            self.statusbar.pop(self.status_context)
            self.statusbar.push(self.status_context, f"{len(results)} {_('results')}")
            
            # LIMPIEZA AGRESIVA después de mostrar todos los resultados
            self._aggressive_cleanup_after_search()
        
        return False  # No repetir este timeout
    
    def _aggressive_cleanup_after_search(self):
        """Limpieza AGRESIVA de memoria después de búsqueda"""
        def cleanup():
            time.sleep(1.5)  # Esperar a que se muestren los resultados
            
            print("\n[MEMORY] Limpieza post-búsqueda...")
            
            # 1. Cerrar caché APT si existe
            try:
                if hasattr(self.catalog, 'apt_manager'):
                    if hasattr(self.catalog.apt_manager, '_apt_cache'):
                        if self.catalog.apt_manager._apt_cache is not None:
                            self.catalog.apt_manager._apt_cache.close()
                            self.catalog.apt_manager._apt_cache = None
                            print("[MEMORY]    ✓ Caché APT cerrado")
            except Exception as e:
                print(f"[MEMORY]    ! Error cerrando APT: {e}")
            
            # 2. Limpiar listas temporales
            try:
                if hasattr(self.catalog.apt_manager, 'available_packages'):
                    self.catalog.apt_manager.available_packages.clear()
                if hasattr(self.catalog.flatpak_manager, 'available_packages'):
                    self.catalog.flatpak_manager.available_packages.clear()
                print("[MEMORY]    ✓ Listas temporales limpiadas")
            except:
                pass
            
            # 3. Garbage collection doble
            import gc
            c1 = gc.collect()
            time.sleep(0.1)
            c2 = gc.collect(2)
            print(f"[MEMORY]    ✓ GC: {c1 + c2} objetos liberados")
            
            print("[MEMORY] ✓ Limpieza post-búsqueda completa\n")
        
        threading.Thread(target=cleanup, daemon=True).start()
    
    def _show_no_results(self, query):
        """Muestra mensaje de sin resultados"""
        no_results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        no_results_box.set_margin_top(80)
        no_results_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("edit-find-symbolic", Gtk.IconSize.DIALOG)
        icon.set_pixel_size(96)
        icon.set_opacity(0.25)
        
        no_results_label = Gtk.Label()
        no_results_label.set_markup(f"<span size='x-large'><b>{_('No results found')}</b></span>")
        
        query_label = Gtk.Label()
        query_label.set_markup(f"<span size='medium'>{_('Try a different search term')}</span>")
        
        no_results_box.pack_start(icon, False, False, 0)
        no_results_box.pack_start(no_results_label, False, False, 0)
        no_results_box.pack_start(query_label, False, False, 0)
        
        self.search_container.pack_start(no_results_box, False, False, 0)
        self.show_all()
        self.statusbar.push(self.status_context, _("No results found"))
    
    def show_app_details(self, app):
        """Muestra los detalles de una aplicación"""
        # Limpiar container
        for child in self.details_container.get_children():
            self.details_container.remove(child)
        
        # Crear widget de detalles
        detail_widget = AppDetailDialog(app, self.catalog, self, self.activity_manager)
        self.detail_widgets[app.app_id] = detail_widget
        
        self.details_container.pack_start(detail_widget, True, True, 0)
        self._navigate_to("Details")
        self.show_all()
    
    def add_activity_widget(self, activity):
        """Añade un widget de actividad"""
        # Remover widgets anteriores excepto el primero
        children = self.activities_container.get_children()
        for child in children[1:]:
            self.activities_container.remove(child)
        
        widget = ActivityWidget(activity)
        self.activities_container.pack_start(widget, False, False, 0)
        self.activities_container.show_all()
    
    def update_activity_counter(self):
        """Actualiza el contador de actividades"""
        count = self.activity_manager.active_count
        self.activity_total_label.set_markup(f"<b>{_('Total:')}</b> {count}")
        
        # Actualizar badge del botón
        if count > 0:
            task_box = Gtk.Box(spacing=4)
            task_box.pack_start(
                Gtk.Image.new_from_icon_name("emblem-downloads-symbolic", Gtk.IconSize.BUTTON),
                False, False, 0
            )
            label = Gtk.Label()
            label.set_markup(f"<b>({count})</b>")
            task_box.pack_start(label, False, False, 0)
            task_box.show_all()
            self.tasks_btn.set_image(task_box)
        else:
            self.tasks_btn.set_image(
                Gtk.Image.new_from_icon_name("emblem-downloads-symbolic", Gtk.IconSize.BUTTON)
            )
    
    def on_app_state_changed(self, app_id):
        """Maneja cambios en el estado de una aplicación"""
        if hasattr(self.catalog, 'all_apps'):
            self.catalog.check_installed_status(self.catalog.all_apps, force_refresh=True)
        
        def refresh_widget(widget, target_app_id):
            if hasattr(widget, 'app'):
                if getattr(widget.app, 'app_id', None) == target_app_id:
                    if hasattr(widget, 'update_status'):
                        widget.update_status()
                        return True
            return False
        
        # Refrescar en todas las vistas
        # Home
        if hasattr(self, 'generic_flowbox'):
            for child in self.generic_flowbox.get_children():
                actual_widget = child.get_child() if hasattr(child, 'get_child') else child
                refresh_widget(actual_widget, app_id)
        
        # Categorías
        for flowbox in self.widget_map.values():
            for child in flowbox.get_children():
                actual_widget = child.get_child() if hasattr(child, 'get_child') else child
                refresh_widget(actual_widget, app_id)
        
        # Detalles
        if self.stack.get_visible_child_name() == "Details":
            if app_id in self.detail_widgets:
                detail_widget = self.detail_widgets[app_id]
                if hasattr(detail_widget, 'update_status'):
                    GLib.idle_add(detail_widget.update_status)
        
        GLib.idle_add(
            self.statusbar.push,
            self.status_context,
            _("Application state updated")
        )
    
    def _show_language_dialog(self, widget):
        """Muestra el diálogo de cambio de idioma"""
        dialog = LanguageDialog(self, SUPPORTED_LANGS)
        response = dialog.run()
        
        if response == Gtk.ResponseType.APPLY:
            selected_lang = dialog.combo.get_active_id()
            if selected_lang:
                _save_to_both_configs(selected_lang, auto_detect=False)
                
                msg_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text=_("Restart required")
                )
                msg_dialog.format_secondary_text(
                    _("The application must be restarted for the language change to take full effect.")
                )
                msg_dialog.run()
                msg_dialog.destroy()
                
                # Reiniciar aplicación
                python = sys.executable
                os.execv(python, [python, os.path.abspath(sys.argv[0])])
        
        dialog.destroy()
    
    def _show_about(self, btn):
        """Muestra el diálogo Acerca de"""
        about = Gtk.AboutDialog()
        about.set_transient_for(self)
        about.set_modal(True)
        about.set_program_name(_("Yelena Store"))
        about.set_version("2.1")
        about.set_copyright("🄯 2026 CuerdOS")
        about.set_comments(_("Modern application manager for CuerdOS\nBeautiful, fast and easy to use"))
        about.set_website("https://cuerdos.github.io/")
        about.set_website_label(_("CuerdOS Website"))
        about.set_license_type(Gtk.License.LGPL_3_0)
        
        if STORE_ICON.exists():
            about.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_size(str(STORE_ICON), 128, 128))
        else:
            about.set_logo_icon_name("applications-system")
        
        about.run()
        about.destroy()
    
    def _open_updates_manager(self, btn):
        """Abre el gestor de actualizaciones"""
        try:
            subprocess.Popen(['cuerdtoken'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            self.statusbar.push(self.status_context, _("Opening Updates Manager..."))
        except FileNotFoundError:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=_("Updates Manager Not Found")
            )
            dialog.format_secondary_text(
                _("The updates manager (cuerdtoken) is not installed or not in PATH.")
            )
            dialog.run()
            dialog.destroy()
            self.statusbar.push(self.status_context, _("Updates Manager not available"))
    
    def _on_delete_event(self, window, event):
        """Maneja el cierre de la ventana - LIMPIEZA AGRESIVA"""
        # Verificar si hay managers inicializados
        if self.activity_manager and self.activity_manager.has_pending_tasks():
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text=_("The pending tasks will be canceled.")
            )
            dialog.format_secondary_text(
                _("There are active installation or uninstallation tasks. "
                  "Closing the program will cancel all of them. Do you want to continue?")
            )
            response = dialog.run()
            dialog.destroy()
            
            if response != Gtk.ResponseType.OK:
                return True  # Cancelar cierre
            
            self.activity_manager.cancel_all_tasks()
        
        # CIERRE INMEDIATO - SIN POPUP
        self._force_cleanup_and_exit()
        return False  # Permitir cierre
    
    def _force_cleanup_and_exit(self):
        """Limpieza AGRESIVA y cierre inmediato del proceso"""
        print("\n" + "="*60)
        print("[CLEANUP] INICIANDO LIMPIEZA AGRESIVA DE MEMORIA")
        print("="*60)
        
        # 1. CANCELAR Y MATAR TODOS LOS THREADS
        print("[CLEANUP] 1. Cancelando threads activos...")
        if hasattr(self, 'activity_manager'):
            self.activity_manager.force_kill_all()
        
        # 2. CERRAR CACHÉ APT INMEDIATAMENTE
        print("[CLEANUP] 2. Cerrando caché APT...")
        if hasattr(self, 'catalog'):
            if hasattr(self.catalog, 'apt_manager'):
                if hasattr(self.catalog.apt_manager, '_apt_cache'):
                    try:
                        if self.catalog.apt_manager._apt_cache is not None:
                            self.catalog.apt_manager._apt_cache.close()
                            del self.catalog.apt_manager._apt_cache
                            self.catalog.apt_manager._apt_cache = None
                            print("[CLEANUP]    ✓ Caché APT cerrado y eliminado")
                    except Exception as e:
                        print(f"[CLEANUP]    ! Error cerrando APT: {e}")
                
                # Limpiar sets de paquetes
                if hasattr(self.catalog.apt_manager, 'installed_packages'):
                    self.catalog.apt_manager.installed_packages.clear()
                if hasattr(self.catalog.apt_manager, 'available_packages'):
                    self.catalog.apt_manager.available_packages.clear()
        
        # 3. LIMPIAR CACHÉ DE FLATPAK
        print("[CLEANUP] 3. Limpiando caché Flatpak...")
        if hasattr(self, 'catalog'):
            if hasattr(self.catalog, 'flatpak_manager'):
                if hasattr(self.catalog.flatpak_manager, 'installed_packages'):
                    self.catalog.flatpak_manager.installed_packages.clear()
                if hasattr(self.catalog.flatpak_manager, 'available_packages'):
                    self.catalog.flatpak_manager.available_packages.clear()
                print("[CLEANUP]    ✓ Caché Flatpak limpiado")
        
        # 4. ELIMINAR CACHÉ DE ICONOS
        print("[CLEANUP] 4. Eliminando caché de iconos...")
        if hasattr(self, 'catalog'):
            if hasattr(self.catalog, 'icon_cache'):
                count = len(self.catalog.icon_cache)
                self.catalog.icon_cache.clear()
                print(f"[CLEANUP]    ✓ {count} iconos eliminados")
        
        # 5. DESTRUIR TODOS LOS WIDGETS
        print("[CLEANUP] 5. Destruyendo widgets...")
        try:
            # Destruir flowbox de apps
            if hasattr(self, 'generic_flowbox'):
                for child in self.generic_flowbox.get_children():
                    child.destroy()
                self.generic_flowbox.destroy()
                del self.generic_flowbox
            
            # Destruir contenedor de búsqueda
            if hasattr(self, 'search_container'):
                for child in self.search_container.get_children():
                    child.destroy()
                self.search_container.destroy()
                del self.search_container
            
            # Destruir stack completo
            if hasattr(self, 'stack'):
                for child in self.stack.get_children():
                    child.destroy()
                self.stack.destroy()
                del self.stack
            
            print("[CLEANUP]    ✓ Widgets destruidos")
        except Exception as e:
            print(f"[CLEANUP]    ! Error destruyendo widgets: {e}")
        
        # 6. LIMPIAR LISTAS DE APLICACIONES
        print("[CLEANUP] 6. Limpiando listas de aplicaciones...")
        if hasattr(self, 'catalog'):
            if hasattr(self.catalog, 'all_apps'):
                count = len(self.catalog.all_apps)
                self.catalog.all_apps.clear()
                print(f"[CLEANUP]    ✓ {count} apps limpiadas de all_apps")
            
            if hasattr(self.catalog, 'popular_apps'):
                count = len(self.catalog.popular_apps)
                self.catalog.popular_apps.clear()
                print(f"[CLEANUP]    ✓ {count} apps limpiadas de popular_apps")
            
            if hasattr(self.catalog, 'categories'):
                self.catalog.categories.clear()
                print("[CLEANUP]    ✓ Categorías limpiadas")
        
        # 7. FORZAR GARBAGE COLLECTION MÚLTIPLE
        print("[CLEANUP] 7. Ejecutando garbage collection...")
        import gc
        
        # Primera pasada
        collected1 = gc.collect()
        print(f"[CLEANUP]    - Pasada 1: {collected1} objetos")
        
        # Segunda pasada
        collected2 = gc.collect()
        print(f"[CLEANUP]    - Pasada 2: {collected2} objetos")
        
        # Tercera pasada (final)
        collected3 = gc.collect()
        print(f"[CLEANUP]    - Pasada 3: {collected3} objetos")
        
        total_collected = collected1 + collected2 + collected3
        print(f"[CLEANUP]    ✓ Total: {total_collected} objetos liberados")
        
        # 8. LIMPIAR REFERENCIAS A OBJETOS GRANDES
        print("[CLEANUP] 8. Eliminando referencias...")
        try:
            if hasattr(self, 'catalog'):
                del self.catalog
            if hasattr(self, 'activity_manager'):
                del self.activity_manager
            print("[CLEANUP]    ✓ Referencias eliminadas")
        except:
            pass
        
        # 9. FORZAR SINCRONIZACIÓN DEL SISTEMA
        print("[CLEANUP] 9. Sincronizando sistema...")
        try:
            subprocess.run(['sync'], timeout=1, check=False, 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[CLEANUP]    ✓ Sistema sincronizado")
        except:
            pass
        
        # 10. GARBAGE COLLECTION FINAL
        print("[CLEANUP] 10. GC final...")
        final_collected = gc.collect(2)  # Generación 2 (más profundo)
        print(f"[CLEANUP]    ✓ {final_collected} objetos finales liberados")
        
        print("="*60)
        print("[CLEANUP] LIMPIEZA COMPLETA - TERMINANDO PROCESO")
        print("="*60 + "\n")
        
        # 11. SALIR INMEDIATAMENTE
        import sys
        sys.exit(0)

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal"""
    win = YelenaStoreWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    
    # Asegurar que el icono se establezca correctamente después de realizar la ventana
    # Esto es crucial para docklike y otros plugins de XFCE
    def set_icon_after_realize():
        try:
            window = win.get_window()
            if window:
                # Establecer el icono de la ventana X11/Wayland
                window.set_icon_name("yel-store")
                
                # Para docklike: establecer la propiedad _NET_WM_ICON_NAME
                if hasattr(window, 'set_utf8_property'):
                    try:
                        window.set_utf8_property("_NET_WM_ICON_NAME", "yel-store")
                    except:
                        pass
        except Exception as e:
            print(f"[ICON] Post-realize icon setup: {e}")
        return False
    
    GLib.idle_add(set_icon_after_realize)
    
    Gtk.main()

if __name__ == "__main__":
    main()