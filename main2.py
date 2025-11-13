import argparse
import sys
import os
import json
import urllib.request
import urllib.error
from collections import deque

def fetch_package_info(package_name, repo_url, version):
    """
    Получает информацию о пакете из npm реестра
    """
    try:
        # Формируем URL для получения информации о пакете
        if repo_url.endswith('/'):
            repo_url = repo_url[:-1]
        
        package_url = f"{repo_url}/{package_name}"
        
        print(f"Запрос информации о пакете: {package_url}")
        
        # Выполняем HTTP-запрос
        with urllib.request.urlopen(package_url) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        return data
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Пакет '{package_name}' не найден в репозитории")
        else:
            raise ValueError(f"Ошибка HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise ValueError(f"Ошибка подключения к репозиторию: {e.reason}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Ошибка парсинга JSON ответа: {e}")
    except Exception as e:
        raise ValueError(f"Ошибка при получении данных: {e}")

def get_package_version_info(package_data, version):
    """
    Получает информацию о конкретной версии пакета
    """
    try:
        if version == 'latest':
            # Используем последнюю версию
            if 'dist-tags' in package_data and 'latest' in package_data['dist-tags']:
                latest_version = package_data['dist-tags']['latest']
                version_info = package_data['versions'].get(latest_version)
            else:
                # Берем последнюю версию из списка
                versions = list(package_data['versions'].keys())
                if not versions:
                    raise ValueError("В пакете нет доступных версий")
                latest_version = sorted(versions)[-1]  # Сортируем и берем последнюю
                version_info = package_data['versions'][latest_version]
        else:
            # Используем указанную версию
            version_info = package_data['versions'].get(version)
        
        if not version_info:
            available_versions = list(package_data['versions'].keys())[:5]  # Показываем первые 5 версий
            raise ValueError(f"Версия '{version}' не найдена. Доступные версии: {', '.join(available_versions)}...")
        
        return version_info
        
    except Exception as e:
        raise ValueError(f"Ошибка при получении информации о версии: {e}")

def extract_dependencies(version_info):
    """
    Извлекает прямые зависимости из информации о версии пакета
    """
    dependencies = {}
    
    # Проверяем различные возможные места хранения зависимостей
    if 'dependencies' in version_info:
        dependencies.update(version_info['dependencies'])
    
    if 'devDependencies' in version_info:
        dependencies.update(version_info['devDependencies'])
    
    if 'peerDependencies' in version_info:
        dependencies.update(version_info['peerDependencies'])
    
    return dependencies

def load_test_repository(file_path):
    """
    Загружает тестовый репозиторий из файла
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        raise ValueError(f"Файл тестового репозитория не найден: {file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Ошибка парсинга JSON в файле: {file_path}")
    except Exception as e:
        raise ValueError(f"Ошибка загрузки тестового репозитория: {e}")

def build_dependency_graph(start_package, repo_url, version, filter_str, test_repo=False):
    """
    Строит граф зависимостей с помощью DFS без рекурсии
    """
    graph = {}
    visited = set()
    stack = deque([(start_package, version)])
    cyclic_dependencies = set()
    
    while stack:
        current_package, current_version = stack.pop()
        
        # Пропускаем если уже посещали
        if current_package in visited:
            continue
            
        visited.add(current_package)
        
        # Пропускаем пакеты по фильтру
        if filter_str and filter_str in current_package:
            continue
        
        try:
            if test_repo:
                # Режим тестирования - загружаем из файла
                test_data = load_test_repository(repo_url)
                package_data = test_data.get(current_package, {})
                version_info = package_data.get('versions', {}).get(current_version, {})
            else:
                # Режим реального репозитория
                package_data = fetch_package_info(current_package, repo_url, current_version)
                version_info = get_package_version_info(package_data, current_version)
            
            # Извлекаем зависимости
            dependencies = extract_dependencies(version_info)
            graph[current_package] = {
                'version': current_version,
                'dependencies': dependencies
            }
            
            # Добавляем зависимости в стек для дальнейшего обхода
            for dep_name, dep_version in dependencies.items():
                # Пропускаем по фильтру
                if filter_str and filter_str in dep_name:
                    continue
                
                # Проверяем циклические зависимости
                if dep_name in visited:
                    cyclic_dependencies.add((current_package, dep_name))
                    continue
                
                stack.append((dep_name, dep_version))
                
        except Exception as e:
            print(f"Предупреждение: не удалось получить зависимости для {current_package}: {e}")
            graph[current_package] = {
                'version': current_version,
                'dependencies': {},
                'error': str(e)
            }
    
    return graph, cyclic_dependencies

def print_dependency_tree(graph, start_package, cyclic_dependencies):
    """
    Выводит дерево зависимостей в формате ASCII
    """
    print("\n" + "=" * 60)
    print("ГРАФ ЗАВИСИМОСТЕЙ (DFS)")
    print("=" * 60)
    
    def print_node(package, level=0, visited=None):
        if visited is None:
            visited = set()
            
        if package in visited:
            print("  " * level + f"└── {package} [ЦИКЛ]")
            return
            
        visited.add(package)
        
        prefix = "  " * level + "└── "
        package_info = graph.get(package, {})
        version = package_info.get('version', 'unknown')
        print(f"{prefix}{package}@{version}")
        
        if package in graph:
            dependencies = graph[package].get('dependencies', {})
            for i, (dep, dep_version) in enumerate(dependencies.items()):
                is_last = i == len(dependencies) - 1
                dep_prefix = "  " * (level + 1) + ("└── " if is_last else "├── ")
                
                # Проверяем циклическую зависимость
                is_cyclic = (package, dep) in cyclic_dependencies
                cyclic_marker = " [ЦИКЛ]" if is_cyclic else ""
                
                print(f"{dep_prefix}{dep}@{dep_version}{cyclic_marker}")
                
                if dep in graph and not is_cyclic:
                    print_node(dep, level + 2, visited.copy())
    
    print_node(start_package)

def analyze_graph_statistics(graph, cyclic_dependencies):
    """
    Анализирует статистику графа зависимостей
    """
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ГРАФА")
    print("=" * 60)
    
    total_packages = len(graph)
    total_dependencies = sum(len(pkg.get('dependencies', {})) for pkg in graph.values())
    packages_with_errors = sum(1 for pkg in graph.values() if 'error' in pkg)
    
    print(f"Всего пакетов в графе: {total_packages}")
    print(f"Всего зависимостей: {total_dependencies}")
    print(f"Циклических зависимостей: {len(cyclic_dependencies)}")
    print(f"Пакетов с ошибками: {packages_with_errors}")
    
    if cyclic_dependencies:
        print("\nЦиклические зависимости:")
        for parent, child in cyclic_dependencies:
            print(f"  {parent} -> {child}")

def main():
    """Основная функция программы"""
    
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(
        description='Инструмент визуализации графа зависимостей пакетов',
        epilog='Пример использования: python dependency_analyzer.py --package-name React --repo-url npmjs.org --version 1.0.0'
    )
    
    # Добавляем все необходимые параметры согласно требованиям
    
    # 1. Имя анализируемого пакета (необязательный параметр)
    parser.add_argument(
        '--package-name',
        type=str,
        default='example-package',  # необязательный параметр
        help='Имя анализируемого пакета (например: React, lodash)'
    )
    
    # 2. URL-адрес репозитория или путь к файлу
    parser.add_argument(
        '--repo-url',
        type=str,
        default='https://registry.npmjs.org',  # Значение по умолчанию
        help='URL-адрес репозитория или путь к файлу тестового репозитория'
    )
    
    # 3. Режим работы с тестовым репозиторием (флаг)
    parser.add_argument(
        '--test-repo',
        action='store_true',  # Флаг - если указан, то True
        default=False,
        help='Режим работы с тестовым репозиторием'
    )
    
    # 4. Версия пакета
    parser.add_argument(
        '--version',
        type=str,
        default='latest',  # По умолчанию последняя версия
        help='Версия пакета (например: 1.0.0, latest)'
    )
    
    # 5. Имя сгенерированного файла с изображением графа
    parser.add_argument(
        '--output',
        type=str,
        default='dependency_graph.png',
        help='Имя сгенерированного файла с изображением графа'
    )
    
    # 6. Режим вывода зависимостей в формате ASCII-дерева (флаг)
    parser.add_argument(
        '--show-tree',
        action='store_true',
        default=False,
        help='Режим вывода зависимостей в формате ASCII-дерева'
    )
    
    # 7. Подстрока для фильтрации пакетов
    parser.add_argument(
        '--filter',
        type=str,
        default='',
        help='Подстрока для фильтрации пакетов (например: "dev-", "test")'
    )
    
    try:
        # Парсим аргументы командной строки
        args = parser.parse_args()
        
        # ВАЛИДАЦИЯ ПАРАМЕТРОВ
        
        # Проверяем, что имя пакета не пустое
        if not args.package_name.strip():
            raise ValueError("Имя пакета не может быть пустым")
        
        # Проверяем, что URL репозитория валидный (базовая проверка)
        if args.repo_url and not (args.repo_url.startswith('http://') or 
                                args.repo_url.startswith('https://') or
                                os.path.exists(args.repo_url)):
            print(f"Предупреждение: URL репозитория '{args.repo_url}' может быть некорректным", file=sys.stderr)
        
        # Проверяем расширение выходного файла
        if not args.output.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
            print(f"Предупреждение: выходной файл '{args.output}' имеет нестандартное расширение", file=sys.stderr)
        
        # Проверяем версию пакета (базовая валидация)
        if args.version != 'latest' and not any(c.isdigit() for c in args.version):
            print(f"Предупреждение: версия '{args.version}' может быть некорректной", file=sys.stderr)
        
        # ЭТАП 3: ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ
        
        print("=" * 50)
        print("ЭТАП 3: ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ")
        print("=" * 50)
        
        # Строим граф зависимостей
        print(f"Построение графа зависимостей для '{args.package_name}'...")
        graph, cyclic_dependencies = build_dependency_graph(
            args.package_name, 
            args.repo_url, 
            args.version, 
            args.filter,
            args.test_repo
        )
        
        # Выводим результаты
        print_dependency_tree(graph, args.package_name, cyclic_dependencies)
        analyze_graph_statistics(graph, cyclic_dependencies)
        
        # Демонстрация работы с тестовым репозиторием
        if args.test_repo:
            print("\n" + "=" * 60)
            print("РЕЖИМ ТЕСТИРОВАНИЯ АКТИВИРОВАН")
            print("=" * 60)
            print("Используется тестовый репозиторий из файла")
            print("Пакеты представлены заглавными латинскими буквами")
        
        print("\nЭтап 3 завершен успешно!")
        print("Граф зависимостей построен с учетом транзитивности")
        
    except argparse.ArgumentError as e:
        # Обработка ошибок парсинга аргументов
        print(f"Ошибка в параметрах командной строки: {e}", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
        
    except ValueError as e:
        # Обработка ошибок валидации
        print(f"Ошибка валидации: {e}", file=sys.stderr)
        sys.exit(1)
        
    except Exception as e:
        # Обработка непредвиденных ошибок
        print(f"Непредвиденная ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()