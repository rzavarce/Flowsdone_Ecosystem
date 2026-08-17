#!/usr/bin/env python3
"""
App Complete Architecture Mapper
Propósito: Listar de forma exhaustiva tanto carpetas como archivos dentro de 'app/'
           para auditar capas, DTOs, schemas y casos de uso.
Estilo: Clean Code, SOLID, Typed Python.
"""

from pathlib import Path
from typing import Set


class AppCompleteMapper:
    def __init__(self, target_dir: str = "app", exclude_dirs: Set[str] = None, exclude_files: Set[str] = None):
        self.target_path = Path(target_dir).resolve()
        
        # Filtros de exclusión para mantener el mapa limpio y enfocado en código fuente
        self.exclude_dirs = exclude_dirs or {
            "__pycache__",
            ".pytest_cache",
            ".venv",
            "venv",
            "volumes",
            ".git"
        }
        self.exclude_files = exclude_files or {
            ".DS_Store",
            "*.pyc",
            "__init__.py"  # Descomenta esta línea si SÍ quieres ver los archivos __init__.py
        }

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Aplica patrones de exclusión para archivos."""
        if file_path.name in self.exclude_files:
            return True
        if any(file_path.match(pattern) for pattern in self.exclude_files if "*" in pattern):
            return True
        return False

    def _explore_node(self, current_path: Path, prefix: str = "") -> None:
        """
        Recorre recursivamente imprimiendo tanto directorios como archivos válidos.
        """
        try:
            # Obtener todos los elementos y ordenarlos: Carpetas primero, luego archivos
            all_items = list(current_path.iterdir())
            filtered_items = sorted(
                [
                    item for item in all_items
                    if (item.is_dir() and item.name not in self.exclude_dirs) or
                       (item.is_file() and not self._should_exclude_file(item))
                ],
                key=lambda x: (not x.is_dir(), x.name.lower())
            )
        except PermissionError:
            print(f"{prefix}└── [Permiso Denegado]")
            return

        count = len(filtered_items)
        for index, item in enumerate(filtered_items):
            is_last = (index == count - 1)
            connector = "└── " if is_last else "├── "
            
            if item.is_dir():
                # Imprimir carpeta
                print(f"{prefix}{connector}{item.name}/")
                # Calcular indentación para la descendencia de esta carpeta
                new_prefix = prefix + ("    " if is_last else "│   ")
                self._explore_node(item, new_prefix)
            else:
                # Imprimir archivo
                print(f"{prefix}{connector}{item.name}")

    def analyze(self) -> None:
        """Punto de entrada de ejecución."""
        if not self.target_path.exists() or not self.target_path.is_dir():
            print(f"Error: No se encontró la carpeta '{self.target_path.name}' en: {self.target_path}")
            return

        print("=" * 80)
        print(f"AUDITORÍA DE ARQUITECTURA COMPLETA (Carpetas y Archivos) - {self.target_path.name}/")
        print("=" * 80)
        
        print(f"{self.target_path.name}/")
        self._explore_node(self.target_path)
        
        print("=" * 80)


if __name__ == "__main__":
    # Por defecto omite los __init__.py para no saturar la vista. 
    # Si deseas verlos, limpia el conjunto 'exclude_files' en la instanciación.
    mapper = AppCompleteMapper(target_dir="./app")
    mapper.analyze()