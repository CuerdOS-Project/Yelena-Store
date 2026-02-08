#!/usr/bin/env python3
"""
Yelena Store - Motor de gestión de paquetes
Lógica completamente reescrita para APT y Flatpak
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GdkPixbuf
import threading
import subprocess
import json
import urllib.request
import time
import re
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Set, Tuple
from enum import Enum

try:
    from translations import _
except ImportError:
    def _(text): return text

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
STORE_DIR = Path.home() / '.local' / 'share' / 'yelena-store'
CATALOG_DIR = STORE_DIR / 'catalogs'
ICON_CACHE_DIR = STORE_DIR / 'icons'
CATALOG_DIR.mkdir(parents=True, exist_ok=True)
ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Constantes
MAX_SEARCH_RESULTS = 100
ICON_CACHE_MAX_SIZE = 150
CACHE_REFRESH_INTERVAL = 60  # segundos

# =============================================================================
# ENUMS Y DATACLASSES
# =============================================================================

class PackageType(Enum):
    """Tipo de paquete"""
    APT = "apt"
    FLATPAK = "flatpak"

class InstallStatus(Enum):
    """Estado de instalación"""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    INSTALLING = "installing"
    REMOVING = "removing"

@dataclass
class Application:
    """Representa una aplicación del catálogo"""
    app_id: str
    name: str
    summary: str
    category: str
    pkg_type: PackageType
    icon_url: Optional[str] = None
    icon_name: Optional[str] = None
    version: Optional[str] = None
    installed: bool = False
    download_size: str = "Unknown"
    remote: str = "unknown"
    is_verified: bool = False
    _icon_pixbuf: Optional[GdkPixbuf.Pixbuf] = None
    
    @property
    def icon_pixbuf(self):
        return self._icon_pixbuf
    
    @icon_pixbuf.setter
    def icon_pixbuf(self, value):
        self._icon_pixbuf = value
    
    def __post_init__(self):
        if isinstance(self.pkg_type, str):
            self.pkg_type = PackageType(self.pkg_type)
        if not self.download_size or self.download_size == "Unknown":
            self.download_size = self._estimate_size()
    
    def _estimate_size(self) -> str:
        """Estima el tamaño basado en el tipo de paquete"""
        if self.pkg_type == PackageType.FLATPAK:
            return "≈ 200-800 MB"
        return "≈ 5-50 MB"

@dataclass
class Activity:
    """Representa una actividad de instalación/desinstalación"""
    app_id: str
    name: str
    action: str
    pkg_type: PackageType
    start_time: float
    status: str = "Started"
    end_time: Optional[float] = None
    success: bool = False
    progress: float = 0.0
    error_message: Optional[str] = None
    widget = None
    
    def __post_init__(self):
        if isinstance(self.pkg_type, str):
            self.pkg_type = PackageType(self.pkg_type)

# =============================================================================
# GESTOR DE PAQUETES APT (OPTIMIZADO CON PYTHON-APT)
# =============================================================================

class AptManager:
    """Gestor de paquetes APT optimizado usando python-apt (bajo consumo de RAM)"""
    
    def __init__(self):
        self.cache_updated = False
        self.installed_packages: Set[str] = set()
        self.available_packages: Dict[str, Dict] = {}
        self._last_cache_update = 0
        self._lock = threading.Lock()
        self._apt_cache = None
        self._use_python_apt = self._check_python_apt()
    
    def _check_python_apt(self) -> bool:
        """Verifica si python-apt está disponible"""
        try:
            import apt
            return True
        except ImportError:
            print("Warning: python-apt not available, using fallback mode")
            return False
    
    def is_available(self) -> bool:
        """Verifica si APT está disponible"""
        try:
            if self._use_python_apt:
                import apt
                return True
            else:
                result = subprocess.run(['which', 'apt-get'], 
                                      capture_output=True, timeout=2)
                return result.returncode == 0
        except:
            return False
    
    def update_cache(self, force: bool = False) -> bool:
        """Actualiza la caché de paquetes disponibles"""
        current_time = time.time()
        
        if not force and (current_time - self._last_cache_update) < CACHE_REFRESH_INTERVAL:
            return True
        
        with self._lock:
            try:
                self._update_installed_packages()
                self._last_cache_update = current_time
                self.cache_updated = True
                return True
            except Exception as e:
                print(f"Error actualizando caché APT: {e}")
                return False
    
    def _update_installed_packages(self):
        """Actualiza el conjunto de paquetes instalados"""
        if self._use_python_apt:
            self._update_with_python_apt()
        else:
            self._update_with_subprocess()
    
    def _update_with_python_apt(self):
        """Actualiza usando python-apt (eficiente)"""
        try:
            import apt
            
            if self._apt_cache is None:
                self._apt_cache = apt.Cache()
            else:
                self._apt_cache.open()
            
            self.installed_packages.clear()
            for pkg in self._apt_cache:
                if pkg.is_installed:
                    self.installed_packages.add(pkg.name)
            
        except Exception as e:
            print(f"Error con python-apt: {e}")
            # Fallback a subprocess si falla
            self._update_with_subprocess()
    
    def _update_with_subprocess(self):
        """Actualiza usando subprocess (fallback)"""
        try:
            result = subprocess.run(
                ['dpkg-query', '-W', '-f=${db:Status-Status}\t${Package}\n'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.installed_packages.clear()
                for line in result.stdout.split('\n'):
                    if not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[0].strip() == 'installed':
                        pkg_name = parts[1].strip().split(':')[0]
                        self.installed_packages.add(pkg_name)
        except Exception as e:
            print(f"Error obteniendo paquetes instalados: {e}")
    
    def is_installed(self, package_name: str) -> bool:
        """Verifica si un paquete está instalado"""
        return package_name in self.installed_packages
    
    def search(self, query: str) -> List[Application]:
        """Busca paquetes APT (optimizado)"""
        if self._use_python_apt:
            return self._search_with_python_apt(query)
        else:
            return self._search_with_subprocess(query)
    
    def _search_with_python_apt(self, query: str) -> List[Application]:
        """Busca usando python-apt (rápido y eficiente)"""
        results = []
        seen_packages = set()
        
        try:
            import apt
            
            if self._apt_cache is None:
                self._apt_cache = apt.Cache()
            
            query_lower = query.lower()
            count = 0
            
            for pkg in self._apt_cache:
                if count >= MAX_SEARCH_RESULTS // 2:
                    break
                
                if query_lower in pkg.name.lower():
                    if not self._is_user_application(pkg.name):
                        continue
                    
                    if pkg.name in seen_packages:
                        continue
                    
                    seen_packages.add(pkg.name)
                    
                    # Obtener descripción
                    description = ""
                    if pkg.candidate and pkg.candidate.summary:
                        description = pkg.candidate.summary
                    
                    # Obtener tamaño
                    size = "Unknown"
                    if pkg.candidate and pkg.candidate.size:
                        size_mb = pkg.candidate.size / (1024 * 1024)
                        size = f"≈ {size_mb:.1f} MB"
                    
                    # Obtener versión
                    version = None
                    if pkg.candidate:
                        version = pkg.candidate.version
                    
                    app = Application(
                        app_id=pkg.name,
                        name=self._format_package_name(pkg.name),
                        summary=description[:200] if description else f"Package {pkg.name}",
                        category="System",
                        pkg_type=PackageType.APT,
                        icon_name=self._guess_icon_name(pkg.name),
                        installed=pkg.is_installed,
                        version=version,
                        download_size=size
                    )
                    
                    results.append(app)
                    count += 1
            
            # Liberar memoria después de búsqueda si no hay instalaciones pendientes
            if len(results) > 0:
                # Pequeño delay y luego liberar
                threading.Timer(2.0, self._free_memory_if_idle).start()
        
        except Exception as e:
            print(f"Error en búsqueda python-apt: {e}")
            # Fallback a subprocess
            return self._search_with_subprocess(query)
        
        return results
    
    def _free_memory_if_idle(self):
        """Libera memoria si no hay operaciones activas"""
        try:
            # Solo liberar si no hay instalaciones en curso
            # (verificar con un flag si tienes sistema de tareas activas)
            import gc
            collected = gc.collect()
            print(f"[Memory] Garbage collector: {collected} objetos liberados")
        except Exception as e:
            print(f"Error en limpieza de memoria: {e}")
    
    def _search_with_subprocess(self, query: str) -> List[Application]:
        """Busca usando subprocess (fallback)"""
        results = []
        seen_packages = set()
        
        try:
            result = subprocess.run(
                ['apt-cache', 'search', '--names-only', query],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if not line.strip():
                        continue
                    
                    parts = line.split(' - ', 1)
                    if len(parts) < 2:
                        continue
                    
                    pkg_name = parts[0].strip()
                    description = parts[1].strip()
                    
                    if not self._is_user_application(pkg_name):
                        continue
                    
                    if pkg_name in seen_packages:
                        continue
                    
                    seen_packages.add(pkg_name)
                    pkg_info = self._get_package_info(pkg_name)
                    
                    app = Application(
                        app_id=pkg_name,
                        name=self._format_package_name(pkg_name),
                        summary=description[:200],
                        category="System",
                        pkg_type=PackageType.APT,
                        icon_name=self._guess_icon_name(pkg_name),
                        installed=self.is_installed(pkg_name),
                        version=pkg_info.get('version'),
                        download_size=pkg_info.get('size', 'Unknown')
                    )
                    
                    results.append(app)
                    
                    if len(results) >= MAX_SEARCH_RESULTS // 2:
                        break
        
        except Exception as e:
            print(f"Error en búsqueda APT subprocess: {e}")
        
        return results
    
    def _get_package_info(self, package_name: str) -> Dict:
        """Obtiene información detallada de un paquete (solo subprocess)"""
        info = {}
        try:
            result = subprocess.run(
                ['apt-cache', 'show', package_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        info['version'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Installed-Size:'):
                        size_kb = line.split(':', 1)[1].strip()
                        try:
                            size_mb = int(size_kb) / 1024
                            info['size'] = f"≈ {size_mb:.1f} MB"
                        except:
                            info['size'] = size_kb
        except:
            pass
        
        return info
    
    def _is_user_application(self, pkg_name: str) -> bool:
        """Determina si un paquete es una aplicación de usuario"""
        pkg_lower = pkg_name.lower()
        
        exclude_suffixes = (
            '-dev', '-doc', '-data', '-common', '-dbg', '-dbgsym',
            '-test', '-tools', '-plugins', '-locale', '-l10n'
        )
        
        exclude_prefixes = (
            'lib', 'python-', 'python3-', 'ruby-', 'node-',
            'fonts-', 'gir1.2-', 'php-'
        )
        
        if any(pkg_lower.endswith(s) for s in exclude_suffixes):
            return False
        
        if any(pkg_lower.startswith(p) for p in exclude_prefixes):
            if not any(app in pkg_lower for app in ('office', 'editor', 'viewer', 'player')):
                return False
        
        return True
    
    def _format_package_name(self, pkg_name: str) -> str:
        """Formatea el nombre del paquete para mostrar"""
        name = re.sub(r'^(gnome-|kde-|xfce-|mate-|lxde-)', '', pkg_name)
        name = name.replace('-', ' ').replace('_', ' ')
        return name.title()
    
    def _guess_icon_name(self, pkg_name: str) -> str:
        """Intenta adivinar el nombre del icono"""
        icon_map = {
            'firefox': 'firefox',
            'chromium': 'chromium-browser',
            'gimp': 'gimp',
            'inkscape': 'inkscape',
            'vlc': 'vlc',
            'libreoffice': 'libreoffice-main',
            'thunderbird': 'thunderbird',
            'blender': 'blender',
            'audacity': 'audacity',
        }
        
        pkg_lower = pkg_name.lower()
        for key, icon in icon_map.items():
            if key in pkg_lower:
                return icon
        
        return pkg_name
    
    def install(self, package_name: str, callback=None) -> Tuple[bool, Optional[str]]:
        """Instala un paquete APT usando pkexec (sin alto consumo de RAM)"""
        try:
            # Usar pkexec con apt-get (más eficiente que python-apt para instalación)
            process = subprocess.Popen(
                ['pkexec', 'apt-get', 'install', '-y', package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Buffer lineal para reducir uso de memoria
            )
            
            # Monitorear progreso sin cargar todo en memoria
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if callback and line:
                    callback(line.strip())
            
            returncode = process.wait()
            
            if returncode == 0:
                self.installed_packages.add(package_name)
                # Actualizar caché de python-apt si existe
                if self._apt_cache is not None:
                    try:
                        self._apt_cache.open()
                    except:
                        pass
                
                # IMPORTANTE: Liberar memoria después de instalación
                self._free_memory_after_operation()
                
                return True, None
            else:
                stderr = process.stderr.read()
                self._free_memory_after_operation()  # Liberar memoria incluso en error
                return False, stderr or f"Error code: {returncode}"
        
        except Exception as e:
            self._free_memory_after_operation()
            return False, str(e)
    
    def remove(self, package_name: str, callback=None) -> Tuple[bool, Optional[str]]:
        """Desinstala un paquete APT"""
        try:
            process = subprocess.Popen(
                ['pkexec', 'apt-get', 'remove', '-y', package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Buffer lineal para reducir uso de memoria
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if callback and line:
                    callback(line.strip())
            
            returncode = process.wait()
            
            if returncode == 0:
                self.installed_packages.discard(package_name)
                # Actualizar caché de python-apt si existe
                if self._apt_cache is not None:
                    try:
                        self._apt_cache.open()
                    except:
                        pass
                
                # IMPORTANTE: Liberar memoria después de desinstalación
                self._free_memory_after_operation()
                
                return True, None
            else:
                stderr = process.stderr.read()
                self._free_memory_after_operation()  # Liberar memoria incluso en error
                return False, stderr or f"Error code: {returncode}"
        
        except Exception as e:
            self._free_memory_after_operation()
            return False, str(e)
    
    def _free_memory_after_operation(self):
        """Libera memoria AGRESIVAMENTE después de operaciones"""
        print("\n[MEMORY] Iniciando limpieza agresiva post-operación...")
        
        try:
            # 1. Cerrar y DESTRUIR caché de python-apt
            if self._apt_cache is not None:
                try:
                    self._apt_cache.close()
                    del self._apt_cache
                    self._apt_cache = None
                    print("[MEMORY]    ✓ Caché APT cerrado y destruido")
                except Exception as e:
                    print(f"[MEMORY]    ! Error cerrando APT: {e}")
            
            # 2. Limpiar TODOS los diccionarios
            if hasattr(self, 'available_packages'):
                count = len(self.available_packages)
                self.available_packages.clear()
                print(f"[MEMORY]    ✓ {count} paquetes disponibles limpiados")
            
            # 3. Limpiar sets (mantener solo installed_packages esencial)
            # No limpiar installed_packages para no romper funcionalidad
            
            # 4. Forzar garbage collection TRIPLE
            import gc
            
            # Pasada 1: Generación 0
            c1 = gc.collect(0)
            
            # Pasada 2: Generación 1
            c2 = gc.collect(1)
            
            # Pasada 3: Generación 2 (más profunda)
            c3 = gc.collect(2)
            
            total = c1 + c2 + c3
            print(f"[MEMORY]    ✓ GC: {c1}/{c2}/{c3} = {total} objetos liberados")
            
            # 5. Sincronizar sistema
            try:
                subprocess.run(['sync'], timeout=1, check=False,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("[MEMORY]    ✓ Sistema sincronizado")
            except:
                pass
            
            # 6. Liberar buffers de Python (si es posible)
            try:
                import sys
                sys.stdout.flush()
                sys.stderr.flush()
            except:
                pass
            
            print("[MEMORY] ✓ Limpieza post-operación completa\n")
            
        except Exception as e:
            print(f"[MEMORY] Error en limpieza: {e}\n")

# =============================================================================
# GESTOR DE PAQUETES FLATPAK
# =============================================================================

class FlatpakManager:
    """Gestor de paquetes Flatpak completamente reescrito"""
    
    def __init__(self):
        self.installed_packages: Set[str] = set()
        self.remotes: List[str] = []
        self._last_cache_update = 0
        self._lock = threading.Lock()
    
    def is_available(self) -> bool:
        """Verifica si Flatpak está disponible"""
        try:
            result = subprocess.run(['which', 'flatpak'],
                                  capture_output=True, timeout=2)
            return result.returncode == 0
        except:
            return False
    
    def update_cache(self, force: bool = False) -> bool:
        """Actualiza la caché de paquetes Flatpak"""
        current_time = time.time()
        
        if not force and (current_time - self._last_cache_update) < CACHE_REFRESH_INTERVAL:
            return True
        
        with self._lock:
            try:
                self._update_installed_packages()
                self._update_remotes()
                self._last_cache_update = current_time
                return True
            except Exception as e:
                print(f"Error actualizando caché Flatpak: {e}")
                return False
    
    def _update_installed_packages(self):
        """Actualiza el conjunto de paquetes instalados"""
        try:
            result = subprocess.run(
                ['flatpak', 'list', '--app', '--columns=application'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.installed_packages.clear()
                for line in result.stdout.split('\n'):
                    app_id = line.strip()
                    if app_id and not self._is_runtime(app_id):
                        self.installed_packages.add(app_id)
        except Exception as e:
            print(f"Error obteniendo Flatpaks instalados: {e}")
    
    def _update_remotes(self):
        """Actualiza la lista de remotes disponibles"""
        try:
            result = subprocess.run(
                ['flatpak', 'remotes', '--columns=name'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self.remotes = [
                    line.strip() for line in result.stdout.split('\n')
                    if line.strip() and line.strip() != 'Name'
                ]
        except Exception as e:
            print(f"Error obteniendo remotes: {e}")
    
    def is_installed(self, app_id: str) -> bool:
        """Verifica si una aplicación Flatpak está instalada"""
        return app_id in self.installed_packages
    
    def search(self, query: str) -> List[Application]:
        """Busca aplicaciones Flatpak"""
        results = []
        seen_apps = set()
        
        try:
            result = subprocess.run(
                ['flatpak', 'search', query],
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    if not line.strip():
                        continue
                    
                    # Flatpak search devuelve formato: Name\tDescription\tApp ID\tVersion\tBranch\tRemotes
                    parts = [p.strip() for p in line.split('\t') if p.strip()]
                    
                    if len(parts) < 3:
                        continue
                    
                    name = parts[0]
                    description = parts[1] if len(parts) > 1 else ""
                    app_id = parts[2] if len(parts) > 2 else ""
                    
                    # Filtrar headers y runtimes
                    if app_id.lower() in ['application', 'app id', 'id']:
                        continue
                    
                    if not app_id or self._is_runtime(app_id):
                        continue
                    
                    if app_id in seen_apps:
                        continue
                    
                    seen_apps.add(app_id)
                    
                    # Determinar remote (flathub por defecto)
                    remote = "flathub"
                    if len(parts) > 5:
                        remote = parts[5]
                    
                    # Crear aplicación
                    app = Application(
                        app_id=app_id,
                        name=name,
                        summary=description[:200] or _("Flatpak Application"),
                        category="Applications",
                        pkg_type=PackageType.FLATPAK,
                        icon_url=self._get_icon_url(app_id),
                        icon_name=app_id.split('.')[-1],
                        installed=self.is_installed(app_id),
                        remote=remote,
                        is_verified=(remote == "flathub")
                    )
                    
                    results.append(app)
                    
                    if len(results) >= MAX_SEARCH_RESULTS // 2:
                        break
        
        except Exception as e:
            print(f"Error en búsqueda Flatpak: {e}")
        
        return results
    
    def _is_runtime(self, app_id: str) -> bool:
        """Determina si un ID es runtime o extensión"""
        runtime_patterns = [
            '.BaseApp', '.Sdk', '.Platform', '.Extension',
            '.Runtime', '.Locale', '.Debug'
        ]
        return any(pattern in app_id for pattern in runtime_patterns)
    
    def _get_icon_url(self, app_id: str) -> str:
        """Obtiene la URL del icono de Flathub"""
        return f"https://dl.flathub.org/repo/appstream/x86_64/icons/128x128/{app_id}.png"
    
    def install(self, app_id: str, remote: str = "flathub", callback=None) -> Tuple[bool, Optional[str]]:
        """Instala una aplicación Flatpak"""
        try:
            process = subprocess.Popen(
                ['flatpak', 'install', '-y', remote, app_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Buffer lineal
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if callback and line:
                    callback(line.strip())
            
            returncode = process.wait()
            
            if returncode == 0:
                self.installed_packages.add(app_id)
                # Limpiar memoria después de instalación
                self._free_memory_flatpak()
                return True, None
            else:
                stderr = process.stderr.read()
                self._free_memory_flatpak()
                return False, stderr or f"Error code: {returncode}"
        
        except Exception as e:
            self._free_memory_flatpak()
            return False, str(e)
    
    def remove(self, app_id: str, callback=None) -> Tuple[bool, Optional[str]]:
        """Desinstala una aplicación Flatpak"""
        try:
            process = subprocess.Popen(
                ['flatpak', 'uninstall', '-y', app_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Buffer lineal
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if callback and line:
                    callback(line.strip())
            
            returncode = process.wait()
            
            if returncode == 0:
                self.installed_packages.discard(app_id)
                # Limpiar memoria después de desinstalación
                self._free_memory_flatpak()
                return True, None
            else:
                stderr = process.stderr.read()
                self._free_memory_flatpak()
                return False, stderr or f"Error code: {returncode}"
        
        except Exception as e:
            self._free_memory_flatpak()
            return False, str(e)
    
    def _free_memory_flatpak(self):
        """Libera memoria después de operaciones Flatpak"""
        print("[MEMORY] Limpieza post-Flatpak...")
        
        try:
            # Limpiar diccionario de paquetes disponibles
            if hasattr(self, 'available_packages'):
                self.available_packages.clear()
            
            # Garbage collection
            import gc
            collected = gc.collect(2)
            print(f"[MEMORY]    ✓ {collected} objetos liberados")
            
            # Sync
            try:
                subprocess.run(['sync'], timeout=1, check=False,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass
            
            print("[MEMORY] ✓ Limpieza post-Flatpak completa")
        except Exception as e:
            print(f"[MEMORY] Error: {e}")

# =============================================================================
# GESTOR DE ACTIVIDADES
# =============================================================================

class ActivityManager:
    """Gestor de actividades de instalación/desinstalación"""
    
    def __init__(self, parent_window=None):
        self.activities: List[Activity] = []
        self.parent_window = parent_window
        self.active_count = 0
        self._lock = threading.Lock()
        self.running_tasks: Dict[str, threading.Thread] = {}
        self.max_concurrent_apt = 1  # Máximo de tareas APT simultáneas (APT no soporta múltiples dpkg)
        self.max_concurrent_flatpak = 3  # Máximo de tareas Flatpak simultáneas
        self.apt_semaphore = threading.Semaphore(self.max_concurrent_apt)
        self.flatpak_semaphore = threading.Semaphore(self.max_concurrent_flatpak)
    
    def set_gui_hooks(self, parent_window):
        """Establece la ventana padre para callbacks"""
        self.parent_window = parent_window
    
    def has_pending_tasks(self) -> bool:
        """Verifica si hay tareas pendientes"""
        return self.active_count > 0
    
    def start_activity(self, app: Application, action: str) -> Activity:
        """Inicia una nueva actividad"""
        activity = Activity(
            app_id=app.app_id,
            name=app.name,
            action=action,
            pkg_type=app.pkg_type,
            start_time=time.time()
        )
        
        with self._lock:
            self.activities.insert(0, activity)
            self.active_count += 1
        
        if self.parent_window:
            GLib.idle_add(self.parent_window.add_activity_widget, activity)
            GLib.idle_add(self.parent_window.update_activity_counter)
        
        return activity
    
    def finish_activity(self, activity: Activity, success: bool, error_msg: Optional[str] = None):
        """Finaliza una actividad"""
        activity.end_time = time.time()
        activity.success = success
        activity.error_message = error_msg
        activity.status = _("Completed") if success else _("Failed")
        
        with self._lock:
            self.active_count = max(0, self.active_count - 1)
            if activity.app_id in self.running_tasks:
                del self.running_tasks[activity.app_id]
        
        if self.parent_window and activity.widget:
            GLib.idle_add(activity.widget.update_status)
            GLib.idle_add(self.parent_window.update_activity_counter)
        
        if success and self.parent_window:
            GLib.idle_add(self.parent_window.on_app_state_changed, activity.app_id)
    
    def execute_package_action(self, app: Application, action: str, catalog_manager):
        """Ejecuta una acción sobre un paquete con soporte de multitasking"""
        if app.app_id in self.running_tasks:
            return
        
        activity = self.start_activity(app, action)
        
        def worker():
            # Usar semáforo según el tipo de paquete
            semaphore = self.apt_semaphore if app.pkg_type == PackageType.APT else self.flatpak_semaphore
            
            try:
                # Adquirir semáforo (esperar si hay demasiadas tareas concurrentes)
                semaphore.acquire()
                
                # Actualizar estado en UI
                if app.pkg_type == PackageType.APT:
                    GLib.idle_add(
                        activity.__setattr__, 'status',
                        _("Waiting for APT lock...") if not semaphore._value else _("Installing...")
                    )
                
                if app.pkg_type == PackageType.APT:
                    manager = catalog_manager.apt_manager
                else:
                    manager = catalog_manager.flatpak_manager
                
                if action == "install":
                    success, error_msg = manager.install(
                        app.app_id if app.pkg_type == PackageType.FLATPAK else app.app_id,
                        app.remote if app.pkg_type == PackageType.FLATPAK else None
                    )
                else:  # remove
                    success, error_msg = manager.remove(app.app_id)
                
                self.finish_activity(activity, success, error_msg)
                
                if success:
                    GLib.idle_add(setattr, app, 'installed', action == "install")
                    GLib.idle_add(catalog_manager.update_cache, True)
            
            except Exception as e:
                self.finish_activity(activity, False, str(e))
            
            finally:
                # Liberar semáforo
                semaphore.release()
        
        thread = threading.Thread(target=worker, daemon=True)
        self.running_tasks[app.app_id] = thread
        thread.start()
    
    def cancel_all_tasks(self):
        """Cancela todas las tareas pendientes y libera recursos"""
        print(f"[ActivityManager] Cancelando {len(self.activities)} tareas...")
        
        # Marcar todas las actividades como canceladas
        with self._lock:
            for activity in self.activities[:]:
                if activity.status not in [_("Completed"), _("Failed")]:
                    activity.status = _("Canceled")
                    activity.progress = 0.0
        
        # Intentar detener threads activos
        for app_id, thread in list(self.running_tasks.items()):
            if thread.is_alive():
                # Los threads daemon se detendrán cuando el programa termine
                print(f"[ActivityManager] Thread {app_id} aún activo")
        
        # Limpiar diccionario de tareas
        self.running_tasks.clear()
        
        # Liberar semáforos
        try:
            # Liberar APT semaphore
            while self.apt_semaphore._value < self.max_concurrent_apt:
                try:
                    self.apt_semaphore.release()
                except:
                    break
            
            # Liberar Flatpak semaphore
            while self.flatpak_semaphore._value < self.max_concurrent_flatpak:
                try:
                    self.flatpak_semaphore.release()
                except:
                    break
        except Exception as e:
            print(f"[ActivityManager] Error liberando semáforos: {e}")
        
        # Limpiar lista de actividades
        with self._lock:
            self.activities.clear()
            self.active_count = 0
        
        print("[ActivityManager] Todas las tareas canceladas")
    
    def force_kill_all(self):
        """MATA TODOS LOS THREADS Y PROCESOS - LIMPIEZA AGRESIVA"""
        print("[ActivityManager] FORZANDO TERMINACIÓN DE TODOS LOS THREADS...")
        
        # 1. Cancelar todas las tareas
        self.cancel_all_tasks()
        
        # 2. Matar todos los subprocesos de instalación/desinstalación
        try:
            # Matar procesos apt-get
            subprocess.run(['pkill', '-9', 'apt-get'], 
                         timeout=1, check=False,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Matar procesos flatpak
            subprocess.run(['pkill', '-9', 'flatpak'], 
                         timeout=1, check=False,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print("[ActivityManager]    ✓ Subprocesos terminados")
        except:
            pass
        
        # 3. Limpiar TODAS las actividades
        with self._lock:
            self.activities.clear()
            self.running_tasks.clear()
            self.active_count = 0
        
        # 4. Liberar TODOS los semáforos agresivamente
        try:
            # Resetear semáforo APT
            self.apt_semaphore = threading.Semaphore(self.max_concurrent_apt)
            
            # Resetear semáforo Flatpak
            self.flatpak_semaphore = threading.Semaphore(self.max_concurrent_flatpak)
            
            print("[ActivityManager]    ✓ Semáforos reseteados")
        except:
            pass
        
        print("[ActivityManager] ✓ TODOS LOS THREADS TERMINADOS")
    
    def cleanup(self):
        """Limpia todos los recursos del ActivityManager"""
        try:
            self.force_kill_all()
            
            # Forzar garbage collection
            import gc
            gc.collect()
            
            print("[ActivityManager] Cleanup completo")
        except Exception as e:
            print(f"[ActivityManager] Error en cleanup: {e}")

# =============================================================================
# GESTOR DE CATÁLOGO
# =============================================================================

class CatalogManager:
    """Gestor del catálogo de aplicaciones"""
    
    def __init__(self):
        self.apt_manager = AptManager()
        self.flatpak_manager = FlatpakManager()
        self.all_apps: List[Application] = []
        self.popular_apps: List[Application] = []
        self.categories: List[Dict] = []
        self.icon_cache: Dict[str, GdkPixbuf.Pixbuf] = {}
        self.parent_window = None
        self._icon_cache_lock = threading.Lock()
        
        # Inicializar
        self._initialize()
        self._load_categories()
        self._load_popular_apps()
    
    def _initialize(self):
        """Inicializa los gestores"""
        if self.apt_manager.is_available():
            threading.Thread(target=self.apt_manager.update_cache, daemon=True).start()
        
        if self.flatpak_manager.is_available():
            threading.Thread(target=self.flatpak_manager.update_cache, daemon=True).start()
    
    def _load_categories(self):
        """Carga las categorías desde catalog.json"""
        catalog_file = CATALOG_DIR / 'catalog.json'
        
        # Si no existe en el directorio del usuario, buscar en el directorio del programa
        if not catalog_file.exists():
            catalog_file = BASE_DIR / 'catalog.json'
        
        if not catalog_file.exists():
            # Categorías por defecto si no existe el archivo
            self.categories = [
                {"id": "Development", "name": {"en": "Development"}, "icon": "applications-engineering"},
                {"id": "Multimedia", "name": {"en": "Multimedia"}, "icon": "multimedia-volume-control"},
                {"id": "Games", "name": {"en": "Games"}, "icon": "applications-games"},
                {"id": "Office", "name": {"en": "Office"}, "icon": "x-office-document"},
                {"id": "Internet", "name": {"en": "Internet"}, "icon": "network-wireless"},
                {"id": "Graphics", "name": {"en": "Graphics"}, "icon": "applications-graphics"},
                {"id": "Utilities", "name": {"en": "Utilities"}, "icon": "applications-accessories"},
                {"id": "System", "name": {"en": "System"}, "icon": "applications-system"}
            ]
            return
        
        try:
            with open(catalog_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.categories = data.get('categories', [])
        except Exception as e:
            print(f"Error cargando categorías: {e}")
            self.categories = []
    
    def _load_popular_apps(self):
        """Carga las aplicaciones populares desde flatpaks.json (solo Flatpak)"""
        # Buscar flatpaks.json en el directorio del usuario o del programa
        flatpaks_file = CATALOG_DIR / 'flatpaks.json'
        
        if not flatpaks_file.exists():
            flatpaks_file = BASE_DIR / 'flatpaks.json'
        
        if not flatpaks_file.exists():
            print("Archivo flatpaks.json no encontrado")
            return
        
        try:
            with open(flatpaks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                apps_data = data.get('flatpaks', [])
            
            # Obtener idioma actual
            try:
                from translations import translator_instance
                current_lang = translator_instance.current_lang
            except:
                current_lang = 'en'
            
            for app_data in apps_data:
                try:
                    # Obtener summary en el idioma actual
                    summary = app_data.get('summary', {})
                    if isinstance(summary, dict):
                        summary_text = summary.get(current_lang, summary.get('en', ''))
                    else:
                        summary_text = summary
                    
                    app = Application(
                        app_id=app_data['app_id'],
                        name=app_data['name'],
                        summary=summary_text,
                        category=app_data.get('category', 'Applications'),
                        pkg_type=PackageType.FLATPAK,  # Siempre Flatpak
                        icon_url=app_data.get('icon_url'),
                        icon_name=app_data.get('icon_name'),
                        remote=app_data.get('remote', 'flathub'),
                        is_verified=app_data.get('is_verified', False)
                    )
                    self.popular_apps.append(app)
                except Exception as e:
                    print(f"Error cargando flatpak {app_data.get('name', 'unknown')}: {e}")
            
            # Verificar estado de instalación
            self.check_installed_status(self.popular_apps)
            
        except Exception as e:
            print(f"Error cargando flatpaks: {e}")
    
    def get_categories(self) -> List[Dict]:
        """Retorna la lista de categorías"""
        return self.categories
    
    def get_category_packages(self, category_id: str) -> List[Application]:
        """Carga paquetes APT desde catalog.json para una categoría específica"""
        catalog_file = CATALOG_DIR / 'catalog.json'
        
        if not catalog_file.exists():
            catalog_file = BASE_DIR / 'catalog.json'
        
        if not catalog_file.exists():
            print("Archivo catalog.json no encontrado")
            return []
        
        try:
            with open(catalog_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Obtener idioma actual
            try:
                from translations import translator_instance
                current_lang = translator_instance.current_lang
            except:
                current_lang = 'en'
            
            # Buscar la categoría
            for cat in data.get('categories', []):
                if cat.get('id') == category_id:
                    apps = []
                    for pkg_data in cat.get('packages', []):
                        try:
                            # Obtener descripción en el idioma actual
                            description = pkg_data.get('description', {})
                            if isinstance(description, dict):
                                desc_text = description.get(current_lang, description.get('en', ''))
                            else:
                                desc_text = description
                            
                            app = Application(
                                app_id=pkg_data['package_name'],
                                name=pkg_data.get('display_name', pkg_data['package_name']),
                                summary=desc_text,
                                category=category_id,
                                pkg_type=PackageType.APT,  # Siempre APT
                                icon_name=pkg_data.get('icon_name'),
                                is_verified=pkg_data.get('is_verified', False)
                            )
                            apps.append(app)
                        except Exception as e:
                            print(f"Error cargando paquete {pkg_data.get('package_name', 'unknown')}: {e}")
                    
                    # Verificar estado de instalación
                    self.check_installed_status(apps)
                    return apps
            
            return []
            
        except Exception as e:
            print(f"Error cargando paquetes de categoría {category_id}: {e}")
            return []
    
    def set_gui_hooks(self, parent_window):
        """Establece callbacks de GUI"""
        self.parent_window = parent_window
    
    def update_cache(self, force: bool = False):
        """Actualiza las cachés de todos los gestores"""
        def update():
            if self.apt_manager.is_available():
                self.apt_manager.update_cache(force)
            if self.flatpak_manager.is_available():
                self.flatpak_manager.update_cache(force)
        
        threading.Thread(target=update, daemon=True).start()
    
    def check_installed_status(self, apps: List[Application], force_refresh: bool = False):
        """Verifica el estado de instalación de las aplicaciones"""
        if force_refresh:
            self.update_cache(True)
        
        for app in apps:
            if app.pkg_type == PackageType.APT:
                app.installed = self.apt_manager.is_installed(app.app_id)
            elif app.pkg_type == PackageType.FLATPAK:
                app.installed = self.flatpak_manager.is_installed(app.app_id)
    
    def search_packages(self, query: str) -> List[Application]:
        """Busca paquetes en todos los gestores"""
        results = []
        
        def search_apt():
            if self.apt_manager.is_available():
                return self.apt_manager.search(query)
            return []
        
        def search_flatpak():
            if self.flatpak_manager.is_available():
                return self.flatpak_manager.search(query)
            return []
        
        # Buscar en paralelo
        apt_thread = threading.Thread(target=lambda: results.extend(search_apt()))
        flatpak_thread = threading.Thread(target=lambda: results.extend(search_flatpak()))
        
        apt_thread.start()
        flatpak_thread.start()
        
        apt_thread.join(timeout=20)
        flatpak_thread.join(timeout=20)
        
        # Verificar estado de instalación
        self.check_installed_status(results)
        
        return results[:MAX_SEARCH_RESULTS]
    
    def get_icon_pixbuf(self, app: Application, size: int = 64) -> Optional[GdkPixbuf.Pixbuf]:
        """Obtiene el pixbuf del icono de una aplicación"""
        # Verificar caché
        cache_key = f"{app.app_id}_{size}"
        with self._icon_cache_lock:
            if cache_key in self.icon_cache:
                return self.icon_cache[cache_key]
        
        # Intentar cargar icono
        pixbuf = None
        
        # 1. Intentar desde el tema de iconos del sistema
        if app.icon_name:
            try:
                theme = Gtk.IconTheme.get_default()
                pixbuf = theme.load_icon(app.icon_name, size, 0)
            except:
                pass
        
        # 2. Intentar desde URL (Flatpak)
        if not pixbuf and app.icon_url:
            pixbuf = self._download_icon(app.icon_url, size)
        
        # 3. Usar icono genérico
        if not pixbuf:
            try:
                theme = Gtk.IconTheme.get_default()
                pixbuf = theme.load_icon("application-x-executable", size, 0)
            except:
                pass
        
        # Guardar en caché
        if pixbuf:
            with self._icon_cache_lock:
                self.icon_cache[cache_key] = pixbuf
                # Limpiar caché si es muy grande
                if len(self.icon_cache) > ICON_CACHE_MAX_SIZE:
                    # Eliminar las primeras 20 entradas
                    keys = list(self.icon_cache.keys())[:20]
                    for key in keys:
                        del self.icon_cache[key]
        
        return pixbuf
    
    def _download_icon(self, url: str, size: int) -> Optional[GdkPixbuf.Pixbuf]:
        """Descarga un icono desde una URL"""
        try:
            # Usar caché de archivos
            cache_file = ICON_CACHE_DIR / f"{hash(url)}_{size}.png"
            
            if cache_file.exists():
                return GdkPixbuf.Pixbuf.new_from_file_at_size(str(cache_file), size, size)
            
            # Descargar
            req = urllib.request.Request(url, headers={'User-Agent': 'Yelena-Store/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = response.read()
                
                # Guardar en caché
                with open(cache_file, 'wb') as f:
                    f.write(data)
                
                # Cargar pixbuf
                loader = GdkPixbuf.PixbufLoader()
                loader.write(data)
                loader.close()
                pixbuf = loader.get_pixbuf()
                
                if pixbuf:
                    return pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
        
        except Exception as e:
            print(f"Error descargando icono {url}: {e}")
        
        return None
    
    def load_catalog_apps(self) -> List[Application]:
        """Carga aplicaciones del catálogo JSON (si existe)"""
        catalog_file = CATALOG_DIR / 'cuerdapps.json'
        
        if not catalog_file.exists():
            return []
        
        try:
            with open(catalog_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            apps = []
            for app_data in data.get('applications', []):
                try:
                    app = Application(
                        app_id=app_data['app_id'],
                        name=app_data['name'],
                        summary=app_data.get('summary', ''),
                        category=app_data.get('category', 'Applications'),
                        pkg_type=PackageType(app_data.get('pkg_type', 'flatpak')),
                        icon_url=app_data.get('icon_url'),
                        icon_name=app_data.get('icon_name'),
                        version=app_data.get('version'),
                        remote=app_data.get('remote', 'flathub'),
                        is_verified=app_data.get('is_verified', False)
                    )
                    apps.append(app)
                except Exception as e:
                    print(f"Error cargando app {app_data.get('name', 'unknown')}: {e}")
            
            self.all_apps = apps
            self.check_installed_status(apps)
            
            return apps
        
        except Exception as e:
            print(f"Error cargando catálogo: {e}")
            return []
