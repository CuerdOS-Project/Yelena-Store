#!/usr/bin/env python3
"""
Yelena Store - Widgets de interfaz
Diseño optimizado para pantallas pequeñas
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
from pathlib import Path
import os
import sys

try:
    from translations import _, translator_instance
except ImportError:
    def _(text): return text
    class DummyTranslator:
        current_lang = "en"
        def save_language(self, lang): print(f"Language set to {lang} (dummy)")
    translator_instance = DummyTranslator()

BASE_DIR = Path(__file__).resolve().parent

# =============================================================================
# WIDGET DE ACTIVIDAD
# =============================================================================

class ActivityWidget(Gtk.Box):
    """Widget compacto de actividad para pantallas pequeñas"""
    
    def __init__(self, activity):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.activity = activity
        activity.widget = self
        
        # Márgenes reducidos para pantallas pequeñas
        self.set_margin_top(3)
        self.set_margin_bottom(3)
        self.set_margin_start(6)
        self.set_margin_end(6)
        
        # Frame compacto
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        
        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        inner_box.set_margin_top(6)
        inner_box.set_margin_bottom(6)
        inner_box.set_margin_start(6)
        inner_box.set_margin_end(6)
        
        # Icono pequeño
        icon = Gtk.Image.new_from_icon_name(
            "emblem-downloads" if activity.action == "install" else "user-trash",
            Gtk.IconSize.MENU
        )
        
        # Info box compacto
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.name_label = Gtk.Label()
        action_verb = _("Installing") if activity.action == "install" else _("Removing")
        self.name_label.set_markup(f"<b>{activity.name}</b>")
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.set_ellipsize(3)  # Ellipsize al final
        self.name_label.set_max_width_chars(25)
        
        self.status_label = Gtk.Label(label=f"{action_verb}")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.get_style_context().add_class("dim-label")
        
        info_box.pack_start(self.name_label, False, False, 0)
        info_box.pack_start(self.status_label, False, False, 0)
        
        # Progress bar compacto
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_pulse_step(0.1)
        self.progress_bar.set_size_request(100, 8)
        self.progress_bar.set_valign(Gtk.Align.CENTER)
        
        inner_box.pack_start(icon, False, False, 0)
        inner_box.pack_start(info_box, True, True, 0)
        inner_box.pack_end(self.progress_bar, False, False, 0)
        
        frame.add(inner_box)
        self.pack_start(frame, True, True, 0)
        
        self.pulse_id = GLib.timeout_add(100, self.pulse_progress)
    
    def pulse_progress(self):
        if self.activity.end_time is None:
            self.progress_bar.pulse()
            return True
        return False
    
    def update_status(self):
        if self.pulse_id:
            GLib.source_remove(self.pulse_id)
            self.pulse_id = None
        
        duration = self.activity.end_time - self.activity.start_time
        status_text = _("Completed") if self.activity.success else _("Failed")
        self.status_label.set_markup(f"<b>{status_text}</b> ({duration:.1f}s)")
        self.progress_bar.set_fraction(1.0)

# =============================================================================
# WIDGET DE TARJETA DE APLICACIÓN (COMPACTO)
# =============================================================================

class PackageTileWidget(Gtk.EventBox):
    """Tarjeta compacta de aplicación optimizada para pantallas pequeñas"""
    
    def __init__(self, app, manager, parent_window, activity_manager):
        super().__init__()
        self.app = app
        self.manager = manager
        self.parent_window = parent_window
        self.activity_manager = activity_manager
        
        # Tamaño reducido para pantallas pequeñas
        self.set_size_request(140, 180)
        
        # Frame
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        
        # Box principal
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        
        # Icono
        self.icon = Gtk.Image()
        self.update_icon(size=48)
        
        # Nombre con verificación
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        name_box.set_halign(Gtk.Align.CENTER)
        
        name_label = Gtk.Label()
        name_label.set_markup(f"<span size='small'><b>{self.app.name}</b></span>")
        name_label.set_line_wrap(True)
        name_label.set_max_width_chars(15)
        name_label.set_justify(Gtk.Justification.CENTER)
        name_label.set_ellipsize(3)
        name_label.set_lines(2)
        name_box.pack_start(name_label, False, False, 0)
        
        # Badge de verificación para Flatpak
        if self.app.pkg_type.value == 'flatpak' and hasattr(self.app, 'is_verified'):
            badge_icon = Gtk.Image.new_from_icon_name(
                "emblem-default" if self.app.is_verified else "dialog-warning-symbolic",
                Gtk.IconSize.MENU
            )
            badge_icon.set_tooltip_text(
                _("Verified by Flathub") if self.app.is_verified else _("Unverified source")
            )
            name_box.pack_start(badge_icon, False, False, 0)
        
        # Resumen corto
        summary_label = None
        if self.app.summary:
            summary_label = Gtk.Label()
            summary_text = self.app.summary[:30] + "..." if len(self.app.summary) > 30 else self.app.summary
            summary_label.set_markup(f"<span size='x-small'>{summary_text}</span>")
            summary_label.set_line_wrap(True)
            summary_label.set_max_width_chars(15)
            summary_label.set_justify(Gtk.Justification.CENTER)
            summary_label.set_lines(2)
            summary_label.set_ellipsize(3)
            summary_label.get_style_context().add_class("dim-label")
        
        # Estado
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        status_box.set_halign(Gtk.Align.CENTER)
        
        if self.app.installed:
            check_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.MENU)
            status_label = Gtk.Label()
            status_label.set_markup(f"<small><b>{_('Installed')}</b></small>")
            status_box.pack_start(check_icon, False, False, 0)
            status_box.pack_start(status_label, False, False, 0)
        else:
            download_icon = Gtk.Image.new_from_icon_name("emblem-downloads", Gtk.IconSize.MENU)
            status_label = Gtk.Label(label=_("Available"))
            status_label.set_markup(f"<small>{_('Available')}</small>")
            status_box.pack_start(download_icon, False, False, 0)
            status_box.pack_start(status_label, False, False, 0)
        
        # Tipo de paquete
        type_label = Gtk.Label()
        type_label.set_markup(f"<span size='xx-small' alpha='50%'>({self.app.pkg_type.value.upper()})</span>")
        
        # Ensamblar
        box.pack_start(self.icon, False, False, 0)
        box.pack_start(name_box, False, False, 0)
        if summary_label:
            box.pack_start(summary_label, True, True, 0)
        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 2)
        box.pack_start(status_box, False, False, 0)
        box.pack_start(type_label, False, False, 0)
        
        frame.add(box)
        self.add(frame)
        
        self.connect("button-press-event", self.on_click)
        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
    
    def on_enter(self, widget, event):
        widget.get_window().set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "pointer"))
        widget.get_child().set_shadow_type(Gtk.ShadowType.IN)
    
    def on_leave(self, widget, event):
        widget.get_window().set_cursor(None)
        widget.get_child().set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
    
    def update_icon(self, size=48):
        pixbuf = self.manager.get_icon_pixbuf(self.app, size)
        if pixbuf:
            self.icon.set_from_pixbuf(pixbuf)
    
    def on_click(self, widget, event):
        self.parent_window.show_app_details(self.app)
    
    def update_status(self):
        """Actualiza el estado visual del widget"""
        # Re-construir el widget con el nuevo estado
        for child in self.get_children():
            self.remove(child)
        
        self.__init__(self.app, self.manager, self.parent_window, self.activity_manager)
        self.show_all()

# =============================================================================
# WIDGET DE LISTA DE PAQUETES (MEJORADO PARA BÚSQUEDA)
# =============================================================================

class PackageListWidget(Gtk.ListBoxRow):
    """Widget de lista mejorado con información completa para resultados de búsqueda"""
    
    def __init__(self, app, manager, parent_window, activity_manager):
        super().__init__()
        self.app = app
        self.manager = manager
        self.parent_window = parent_window
        self.activity_manager = activity_manager
        
        # Importante: hacer que la fila no sea seleccionable automáticamente
        self.set_selectable(False)
        self.set_activatable(True)
        
        # Frame para evitar sobreposición
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        
        # Box principal horizontal
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        
        # Icono pequeño
        self.icon = Gtk.Image()
        self.update_icon(size=48)
        
        # Info box (nombre y detalles)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        # Nombre y badges
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{self.app.name}</b>")
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(3)
        name_label.set_max_width_chars(40)
        name_box.pack_start(name_label, False, False, 0)
        
        # Badge de tipo
        type_badge = Gtk.Label()
        type_badge.set_markup(f"<span size='x-small' alpha='60%'>{self.app.pkg_type.value.upper()}</span>")
        name_box.pack_start(type_badge, False, False, 0)
        
        # Badge de verificación
        if self.app.pkg_type.value == 'flatpak' and hasattr(self.app, 'is_verified'):
            verify_icon = Gtk.Image.new_from_icon_name(
                "emblem-default" if self.app.is_verified else "dialog-warning-symbolic",
                Gtk.IconSize.MENU
            )
            name_box.pack_start(verify_icon, False, False, 0)
        
        # Resumen
        summary_label = Gtk.Label()
        summary_text = self.app.summary[:80] + "..." if len(self.app.summary) > 80 else self.app.summary
        summary_label.set_markup(f"<span size='small'>{summary_text}</span>")
        summary_label.set_halign(Gtk.Align.START)
        summary_label.set_ellipsize(3)
        summary_label.set_max_width_chars(50)
        summary_label.get_style_context().add_class("dim-label")
        
        # Información técnica (ID, Nombre de paquete, Peso)
        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        
        # ID del paquete
        id_label = Gtk.Label()
        id_label.set_markup(f"<span size='x-small'><b>ID:</b> {self.app.app_id}</span>")
        id_label.set_halign(Gtk.Align.START)
        id_label.set_ellipsize(3)
        id_label.set_max_width_chars(30)
        id_label.get_style_context().add_class("dim-label")
        details_box.pack_start(id_label, False, False, 0)
        
        # Separador
        sep1 = Gtk.Label()
        sep1.set_markup("<span size='x-small'>•</span>")
        details_box.pack_start(sep1, False, False, 0)
        
        # Tamaño
        size_label = Gtk.Label()
        size_label.set_markup(f"<span size='x-small'><b>{_('Size')}:</b> {self.app.download_size}</span>")
        size_label.set_halign(Gtk.Align.START)
        size_label.get_style_context().add_class("dim-label")
        details_box.pack_start(size_label, False, False, 0)
        
        info_box.pack_start(name_box, False, False, 0)
        info_box.pack_start(summary_label, False, False, 0)
        info_box.pack_start(details_box, False, False, 0)
        
        # Estado e instalación
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right_box.set_valign(Gtk.Align.CENTER)
        
        # Estado
        if self.app.installed:
            status_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.BUTTON)
            status_icon.set_tooltip_text(_("Installed"))
            right_box.pack_start(status_icon, False, False, 0)
        
        # Botón de acción compacto
        self.action_btn = Gtk.Button()
        self.action_btn.set_size_request(100, 32)
        if self.app.installed:
            self.action_btn.set_label(_("Remove"))
            self.action_btn.get_style_context().add_class("destructive-action")
        else:
            self.action_btn.set_label(_("Install"))
            self.action_btn.get_style_context().add_class("suggested-action")
        
        self.action_btn.connect("clicked", self.on_action_clicked)
        right_box.pack_end(self.action_btn, False, False, 0)
        
        # Ensamblar
        main_box.pack_start(self.icon, False, False, 0)
        main_box.pack_start(info_box, True, True, 0)
        main_box.pack_end(right_box, False, False, 0)
        
        frame.add(main_box)
        self.add(frame)
        
        # Conectar clic para ver detalles (solo si no es el botón)
        self.connect("activate", self._on_row_activated)
    
    def _on_row_activated(self, row):
        """Maneja el clic en la fila para mostrar detalles"""
        self.parent_window.show_app_details(self.app)
    
    def update_icon(self, size=48):
        pixbuf = self.manager.get_icon_pixbuf(self.app, size)
        if pixbuf:
            self.icon.set_from_pixbuf(pixbuf)
    
    def on_action_clicked(self, btn):
        action = "remove" if self.app.installed else "install"
        self.activity_manager.execute_package_action(self.app, action, self.manager)
        btn.set_sensitive(False)
    
    def update_status(self):
        """Actualiza el estado del botón"""
        self.action_btn.set_sensitive(True)
        if self.app.installed:
            self.action_btn.set_label(_("Remove"))
            self.action_btn.get_style_context().remove_class("suggested-action")
            self.action_btn.get_style_context().add_class("destructive-action")
        else:
            self.action_btn.set_label(_("Install"))
            self.action_btn.get_style_context().remove_class("destructive-action")
            self.action_btn.get_style_context().add_class("suggested-action")

# =============================================================================
# DIÁLOGO DE DETALLES DE APLICACIÓN (ESTILO TARJETA MEJORADO)
# =============================================================================

class AppDetailWidget(Gtk.Box):
    """Vista de detalles de aplicación usando el estilo de las tarjetas del inicio"""
    
    def __init__(self, app, manager, parent_window, activity_manager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.app = app
        self.manager = manager
        self.parent_window = parent_window
        self.activity_manager = activity_manager
        
        self.build_ui()
    
    def build_ui(self):
        # Scroll container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(16)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        
        # ========== TARJETA PRINCIPAL (Estilo del inicio) ==========
        main_card = Gtk.Frame()
        main_card.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        
        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_box.set_margin_top(16)
        card_box.set_margin_bottom(16)
        card_box.set_margin_start(16)
        card_box.set_margin_end(16)
        
        # Icono grande
        self.icon = Gtk.Image()
        pixbuf = self.manager.get_icon_pixbuf(self.app, 96)
        if pixbuf:
            self.icon.set_from_pixbuf(pixbuf)
        
        # Nombre con verificación
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_box.set_halign(Gtk.Align.CENTER)
        
        name_label = Gtk.Label()
        name_label.set_markup(f"<span size='xx-large'><b>{self.app.name}</b></span>")
        name_label.set_line_wrap(True)
        name_label.set_justify(Gtk.Justification.CENTER)
        name_box.pack_start(name_label, False, False, 0)
        
        # Badge de verificación
        if self.app.pkg_type.value == 'flatpak' and hasattr(self.app, 'is_verified'):
            badge_icon = Gtk.Image.new_from_icon_name(
                "emblem-default" if self.app.is_verified else "dialog-warning-symbolic",
                Gtk.IconSize.LARGE_TOOLBAR
            )
            badge_icon.set_tooltip_text(
                _("Verified by Flathub") if self.app.is_verified else _("Unverified source")
            )
            name_box.pack_start(badge_icon, False, False, 0)
        
        # Resumen
        summary_label = Gtk.Label()
        summary_label.set_markup(f"<span size='medium'>{self.app.summary}</span>")
        summary_label.set_line_wrap(True)
        summary_label.set_max_width_chars(50)
        summary_label.set_justify(Gtk.Justification.CENTER)
        summary_label.get_style_context().add_class("dim-label")
        
        # Separador
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        
        # Estado
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_box.set_halign(Gtk.Align.CENTER)
        
        if self.app.installed:
            check_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.BUTTON)
            status_label = Gtk.Label()
            status_label.set_markup(f"<span size='large'><b>{_('Installed')}</b></span>")
            status_box.pack_start(check_icon, False, False, 0)
            status_box.pack_start(status_label, False, False, 0)
        else:
            download_icon = Gtk.Image.new_from_icon_name("emblem-downloads", Gtk.IconSize.BUTTON)
            status_label = Gtk.Label()
            status_label.set_markup(f"<span size='large'>{_('Available')}</span>")
            status_box.pack_start(download_icon, False, False, 0)
            status_box.pack_start(status_label, False, False, 0)
        
        # Tipo de paquete
        type_label = Gtk.Label()
        type_label.set_markup(f"<span size='small' alpha='70%'>({self.app.pkg_type.value.upper()})</span>")
        
        # Ensamblar tarjeta principal
        card_box.pack_start(self.icon, False, False, 0)
        card_box.pack_start(name_box, False, False, 0)
        card_box.pack_start(summary_label, False, False, 0)
        card_box.pack_start(separator, False, False, 4)
        card_box.pack_start(status_box, False, False, 0)
        card_box.pack_start(type_label, False, False, 0)
        
        main_card.add(card_box)
        content_box.pack_start(main_card, False, False, 0)
        
        # ========== ADVERTENCIA (si no está verificado) ==========
        if self.app.pkg_type.value == 'flatpak' and hasattr(self.app, 'is_verified'):
            if not self.app.is_verified:
                warning_frame = Gtk.Frame()
                warning_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
                
                warning_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                warning_box.set_margin_top(10)
                warning_box.set_margin_bottom(10)
                warning_box.set_margin_start(10)
                warning_box.set_margin_end(10)
                
                warning_icon = Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.DIALOG)
                warning_text = Gtk.Label()
                warning_text.set_markup(
                    f"<span foreground='orange'><b>{_('Unverified Application')}</b></span>\n"
                    f"<span size='small'>{_('This application is not verified. Install at your own risk.')}</span>"
                )
                warning_text.set_line_wrap(True)
                
                warning_box.pack_start(warning_icon, False, False, 0)
                warning_box.pack_start(warning_text, True, True, 0)
                
                warning_frame.add(warning_box)
                content_box.pack_start(warning_frame, False, False, 0)
        
        # ========== INFORMACIÓN TÉCNICA ==========
        info_frame = Gtk.Frame()
        info_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        info_frame.set_label_align(0.02, 0.5)
        
        info_title = Gtk.Label()
        info_title.set_markup(f"<b>{_('Information')}</b>")
        info_frame.set_label_widget(info_title)
        
        info_grid = Gtk.Grid()
        info_grid.set_column_spacing(12)
        info_grid.set_row_spacing(8)
        info_grid.set_margin_top(10)
        info_grid.set_margin_bottom(10)
        info_grid.set_margin_start(10)
        info_grid.set_margin_end(10)
        
        info_items = [
            (_("Package ID"), self.app.app_id),
            (_("Category"), _(self.app.category)),
            (_("Size"), self.app.download_size),
        ]
        
        if self.app.pkg_type.value == 'flatpak':
            if hasattr(self.app, 'remote') and self.app.remote:
                info_items.append((_("Remote"), self.app.remote))
        
        for i, (key, value) in enumerate(info_items):
            key_label = Gtk.Label()
            key_label.set_markup(f"<b>{key}:</b>")
            key_label.set_halign(Gtk.Align.END)
            
            val_label = Gtk.Label(label=value)
            val_label.set_halign(Gtk.Align.START)
            val_label.set_ellipsize(3)
            val_label.set_max_width_chars(35)
            val_label.set_selectable(i == 0)
            
            info_grid.attach(key_label, 0, i, 1, 1)
            info_grid.attach(val_label, 1, i, 1, 1)
        
        info_frame.add(info_grid)
        content_box.pack_start(info_frame, False, False, 0)
        
        scrolled.add(content_box)
        self.pack_start(scrolled, True, True, 0)
        
        # ========== BOTÓN DE ACCIÓN ==========
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        action_box.set_margin_top(12)
        action_box.set_margin_bottom(12)
        action_box.set_margin_start(16)
        action_box.set_margin_end(16)
        
        self.action_btn = Gtk.Button()
        self.action_btn.set_size_request(200, 45)
        
        if self.app.installed:
            self.action_btn.set_label(_("Uninstall"))
            self.action_btn.get_style_context().add_class("destructive-action")
            icon = Gtk.Image.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
        else:
            self.action_btn.set_label(_("Install"))
            self.action_btn.get_style_context().add_class("suggested-action")
            icon = Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON)
        
        self.action_btn.set_image(icon)
        self.action_btn.set_always_show_image(True)
        self.action_btn.connect("clicked", self.on_action_clicked)
        
        action_box.pack_end(self.action_btn, False, False, 0)
        self.pack_end(action_box, False, False, 0)
    
    def on_action_clicked(self, btn):
        action = "remove" if self.app.installed else "install"
        self.activity_manager.execute_package_action(self.app, action, self.manager)
    
    def update_status(self):
        """Regenera la interfaz con el estado actualizado"""
        self.manager.check_installed_status([self.app], force_refresh=True)
        
        for child in self.get_children():
            self.remove(child)
        
        self.build_ui()
        self.show_all()


# Mantener alias para compatibilidad
AppDetailDialog = AppDetailWidget

# =============================================================================
# DIÁLOGO DE SELECCIÓN DE IDIOMA
# =============================================================================

class LanguageDialog(Gtk.Dialog):
    """Diálogo de selección de idioma"""
    
    def __init__(self, parent, supported_langs):
        super().__init__(title=_("Select Language"), transient_for=parent, modal=True)
        self.set_default_size(300, 180)
        self.parent = parent
        
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(15)
        box.set_margin_bottom(15)
        box.set_margin_start(15)
        box.set_margin_end(15)
        
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        
        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner_box.set_margin_top(12)
        inner_box.set_margin_bottom(12)
        inner_box.set_margin_start(12)
        inner_box.set_margin_end(12)
        
        label = Gtk.Label()
        label.set_markup(f"<b>{_('Select your preferred language:')}</b>")
        label.set_halign(Gtk.Align.START)
        
        self.combo = Gtk.ComboBoxText()
        lang_names = {
            "es": "Español",
            "en": "English",
            "pt": "Português",
            "ca": "Català",
            "it": "Italiano",
            "de": "Deutsch"
        }
        
        for lang_code in supported_langs:
            if lang_code in lang_names:
                self.combo.append(lang_code, lang_names[lang_code])
                if hasattr(translator_instance, 'current_lang') and lang_code == translator_instance.current_lang:
                    self.combo.set_active_id(lang_code)
        
        inner_box.pack_start(label, False, False, 0)
        inner_box.pack_start(self.combo, False, False, 0)
        frame.add(inner_box)
        box.pack_start(frame, True, True, 0)
        
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(_("Apply"), Gtk.ResponseType.APPLY)
        
        self.show_all()
