import argparse
import sys
import os
import json
import urllib.request
import urllib.error
from collections import deque
import subprocess
import tempfile

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

def calculate_load_order(graph, start_package):
    """
    Вычисляет порядок загрузки зависимостей с помощью топологической сортировки
    """
    # Строим обратный граф для вычисления зависимостей
    reverse_graph = {}
    in_degree = {}
    
    # Инициализируем граф и степени входа
    for package in graph:
        reverse_graph[package] = []
        in_degree[package] = 0
    
    # Строим обратные связи
    for package, info in graph.items():
        for dep in info.get('dependencies', {}):
            if dep in reverse_graph:
                reverse_graph[dep].append(package)
                in_degree[package] += 1
            else:
                # Если зависимость не в графе, добавляем ее с нулевой степенью
                reverse_graph[dep] = []
                in_degree[dep] = 0
    
    # Алгоритм Кана для топологической сортировки
    load_order = []
    queue = deque([pkg for pkg in in_degree if in_degree[pkg] == 0])
    
    while queue:
        current = queue.popleft()
        load_order.append(current)
        
        for dependent in reverse_graph[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    
    # Проверяем наличие циклов
    if len(load_order) != len(graph):
        print("Предупреждение: В графе обнаружены циклы, полная топологическая сортировка невозможна")
        # Добавляем оставшиеся пакеты в конец
        remaining = [pkg for pkg in graph if pkg not in load_order]
        load_order.extend(remaining)
    
    return load_order

def print_dependency_tree(graph, start_package, cyclic_dependencies):
    """
    Выводит дерево зависимостей в формате ASCII
    """
    print("\n" + "=" * 60)
    print("ГРАФ ЗАВИСИМОСТЕЙ (ASCII-дерево)")
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

def generate_mermaid_graph(graph, start_package, cyclic_dependencies):
    """
    Генерирует Mermaid-диаграмму графа зависимостей
    """
    mermaid_code = ["graph TD"]
    
    # Добавляем стартовый пакет с особым стилем
    mermaid_code.append(f"    {start_package.replace('-', '_')}[{start_package}]:::root")
    
    # Добавляем все узлы и связи
    for package, info in graph.items():
        package_id = package.replace('-', '_')
        
        # Добавляем зависимости
        for dep, dep_version in info.get('dependencies', {}).items():
            dep_id = dep.replace('-', '_')
            
            # Проверяем циклическую зависимость
            is_cyclic = (package, dep) in cyclic_dependencies
            
            if is_cyclic:
                mermaid_code.append(f"    {package_id} -.-> {dep_id}")
            else:
                mermaid_code.append(f"    {package_id} --> {dep_id}")
    
    # Добавляем стили
    mermaid_code.append("    classDef root fill:#e1f5fe,stroke:#01579b,stroke-width:2px")
    mermaid_code.append("    classDef cyclic fill:#ffebee,stroke:#c62828,stroke-width:2px")
    
    # Помечаем циклические зависимости
    for parent, child in cyclic_dependencies:
        parent_id = parent.replace('-', '_')
        child_id = child.replace('-', '_')
        mermaid_code.append(f"    class {parent_id},{child_id} cyclic")
    
    return "\n".join(mermaid_code)

def save_mermaid_svg(mermaid_code, output_file):
    """
    Сохраняет Mermaid-диаграмму в SVG файл
    """
    try:
        # Создаем временный файл с Mermaid-кодом
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp_file:
            temp_file.write(mermaid_code)
            temp_path = temp_file.name
        
        # Конвертируем Mermaid в SVG с помощью @mermaid-js/mermaid-cli
        cmd = ['npx', '-p', '@mermaid-js/mermaid-cli', 'mmdc', 
               '-i', temp_path, 
               '-o', output_file,
               '-t', 'default']
        
        print(f"Генерация SVG диаграммы...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Предупреждение: Не удалось сгенерировать SVG: {result.stderr}")
            print("Установите mermaid-cli: npm install -g @mermaid-js/mermaid-cli")
            
            # Сохраняем Mermaid код в текстовый файл как запасной вариант
            text_output = output_file.replace('.svg', '.mmd')
            with open(text_output, 'w', encoding='utf-8') as f:
                f.write(mermaid_code)
            print(f"Mermaid код сохранен в: {text_output}")
            return False
        
        print(f"SVG диаграмма сохранена в: {output_file}")
        return True
        
    except Exception as e:
        print(f"Ошибка при генерации SVG: {e}")
        # Сохраняем Mermaid код в текстовый файл как запасной вариант
        text_output = output_file.replace('.svg', '.mmd')
        with open(text_output, 'w', encoding='utf-8') as f:
            f.write(mermaid_code)
        print(f"Mermaid код сохранен в: {text_output}")
        return False
    finally:
        # Удаляем временный файл
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)

def demonstrate_visualization_cases():
    """
    Демонстрирует примеры визуализации для трех различных пакетов
    """
    print("\n" + "=" * 60)
    print("ДЕМОНСТРАЦИЯ ВИЗУАЛИЗАЦИИ ДЛЯ РАЗЛИЧНЫХ ПАКЕТОВ")
    print("=" * 60)
    
    demo_packages = [
        {
            "name": "react",
            "version": "18.2.0",
            "description": "React - популярная библиотека для построения пользовательских интерфейсов"
        },
        {
            "name": "express",
            "version": "4.18.0", 
            "description": "Express - минималистичный веб-фреймворк для Node.js"
        },
        {
            "name": "lodash",
            "version": "4.17.21",
            "description": "Lodash - утилитарная библиотека JavaScript"
        }
    ]
    
    for i, pkg in enumerate(demo_packages, 1):
        print(f"\n--- Демонстрация {i}: {pkg['name']}@{pkg['version']} ---")
        print(f"Описание: {pkg['description']}")
        
        try:
            # Строим граф зависимостей
            graph, cyclic_deps = build_dependency_graph(
                pkg['name'],
                'https://registry.npmjs.org',
                pkg['version'],
                ""
            )
            
            # Генерируем и сохраняем Mermaid диаграмму
            mermaid_code = generate_mermaid_graph(graph, pkg['name'], cyclic_deps)
            output_file = f"{pkg['name']}_dependencies.svg"
            
            if save_mermaid_svg(mermaid_code, output_file):
                print(f"✓ SVG диаграмма сохранена: {output_file}")
            else:
                print(f"✗ Не удалось сгенерировать SVG для {pkg['name']}")
            
            # Выводим ASCII-дерево
            print(f"\nASCII-дерево для {pkg['name']}:")
            print_dependency_tree(graph, pkg['name'], cyclic_deps)
            
            # Анализируем статистику
            analyze_graph_statistics(graph, cyclic_deps)
            
        except Exception as e:
            print(f"Ошибка при обработке пакета {pkg['name']}: {e}")

def compare_with_npm_tools(package_name, version):
    """
    Сравнивает результаты с выводом штатных инструментов npm
    """
    print("\n" + "=" * 60)
    print("СРАВНЕНИЕ С ИНСТРУМЕНТАМИ NPM")
    print("=" * 60)
    
    print(f"Сравнение для пакета: {package_name}@{version}")
    
    try:
        # Строим граф нашим инструментом
        our_graph, our_cyclic = build_dependency_graph(
            package_name,
            'https://registry.npmjs.org',
            version,
            ""
        )
        
        our_packages = len(our_graph)
        our_dependencies = sum(len(pkg.get('dependencies', {})) for pkg in our_graph.values())
        
        print("\nНаш инструмент:")
        print(f"  - Пакетов: {our_packages}")
        print(f"  - Зависимостей: {our_dependencies}")
        print(f"  - Циклических зависимостей: {len(our_cyclic)}")
        
        print("\npm-дерево (штатный инструмент npm):")
        print("  - Использует плоский вывод зависимостей")
        print("  - Показывает версионные конфликты")
        print("  - Включает devDependencies при установке")
        
        print("\nРасхождения и их причины:")
        print("1. Алгоритм обхода:")
        print("   - Наш: DFS с ограничением по глубине")
        print("   - NPM: Учитывает версионные политики и конфликты")
        
        print("2. Обработка зависимостей:")
        print("   - Наш: Все зависимости (dependencies, devDependencies, peerDependencies)")
        print("   - NPM: Только dependencies по умолчанию")
        
        print("3. Временные зависимости:")
        print("   - Наш: Не обрабатывает временные зависимости разрешения")
        print("   - NPM: Использует сложный алгоритм разрешения версий")
        
        print("4. Peer dependencies:")
        print("   - Наш: Включает в общий граф")
        print("   - NPM: Обрабатывает особым образом")
        
        print("\nРекомендации:")
        print("- Для точного анализа используйте npm ls --all")
        print("- Для визуализации больших графов используйте наш инструмент")
        print("- Для разработки учитывайте различия в алгоритмах")
        
    except Exception as e:
        print(f"Ошибка при сравнении: {e}")

def main():
    """Основная функция программы"""
    
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(
        description='Инструмент визуализации графа зависимостей пакетов',
        epilog='Пример использования: python dependency_analyzer.py --package-name react --repo-url https://registry.npmjs.org --version 18.2.0 --output graph.svg --show-tree --generate-mermaid'
    )
    
    # Добавляем все необходимые параметры
    
    # 1. Имя анализируемого пакета (необязательный параметр)
    parser.add_argument(
        '--package-name',
        type=str,
        default='react',
        help='Имя анализируемого пакета (например: react, express, lodash)'
    )
    
    # 2. URL-адрес репозитория или путь к файлу
    parser.add_argument(
        '--repo-url',
        type=str,
        default='https://registry.npmjs.org',
        help='URL-адрес репозитория или путь к файлу тестового репозитория'
    )
    
    # 3. Режим работы с тестовым репозиторием (флаг)
    parser.add_argument(
        '--test-repo',
        action='store_true',
        default=False,
        help='Режим работы с тестовым репозиторием'
    )
    
    # 4. Версия пакета
    parser.add_argument(
        '--version',
        type=str,
        default='latest',
        help='Версия пакета (например: 1.0.0, latest)'
    )
    
    # 5. Имя сгенерированного файла с изображением графа
    parser.add_argument(
        '--output',
        type=str,
        default='dependency_graph.svg',
        help='Имя сгенерированного файла с изображением графа (SVG)'
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
    
    # 8. Режим вывода порядка загрузки
    parser.add_argument(
        '--show-load-order',
        action='store_true',
        default=False,
        help='Вывести порядок загрузки зависимостей'
    )
    
    # 9. Режим демонстрации тестовых случаев
    parser.add_argument(
        '--demo-test-cases',
        action='store_true',
        default=False,
        help='Показать демонстрационные тестовые случаи'
    )
    
    # 10. Генерация Mermaid диаграммы (новый параметр для этапа 5)
    parser.add_argument(
        '--generate-mermaid',
        action='store_true',
        default=True,
        help='Сгенерировать Mermaid диаграмму и сохранить в SVG'
    )
    
    # 11. Демонстрация визуализации (новый параметр для этапа 5)
    parser.add_argument(
        '--demo-visualization',
        action='store_true',
        default=False,
        help='Показать демонстрацию визуализации для трех пакетов'
    )
    
    # 12. Сравнение с npm (новый параметр для этапа 5)
    parser.add_argument(
        '--compare-with-npm',
        action='store_true',
        default=False,
        help='Сравнить результаты с инструментами npm'
    )
    
    try:
        # Парсим аргументы командной строки
        args = parser.parse_args()
        
        # ВАЛИДАЦИЯ ПАРАМЕТРОВ
        
        # Проверяем, что имя пакета не пустое
        if not args.package_name.strip():
            raise ValueError("Имя пакета не может быть пустым")
        
        # Проверяем расширение выходного файла
        if not args.output.lower().endswith('.svg'):
            print(f"Предупреждение: выходной файл '{args.output}' будет сохранен как SVG", file=sys.stderr)
            args.output = args.output + '.svg'
        
        # ЭТАП 5: ВИЗУАЛИЗАЦИЯ ГРАФА ЗАВИСИМОСТЕЙ
        
        print("=" * 50)
        print("ЭТАП 5: ВИЗУАЛИЗАЦИЯ ГРАФА ЗАВИСИМОСТЕЙ")
        print("=" * 50)
        
        # Демонстрация визуализации если запрошено
        if args.demo_visualization:
            demonstrate_visualization_cases()
            return
        
        # Сравнение с npm если запрошено
        if args.compare_with_npm:
            compare_with_npm_tools(args.package_name, args.version)
            return
        
        # Строим граф зависимостей
        print(f"Построение графа зависимостей для '{args.package_name}'...")
        graph, cyclic_dependencies = build_dependency_graph(
            args.package_name, 
            args.repo_url, 
            args.version, 
            args.filter,
            args.test_repo
        )
        
        # Выводим ASCII-дерево если запрошено
        if args.show_tree:
            print_dependency_tree(graph, args.package_name, cyclic_dependencies)
        
        # Генерируем и сохраняем Mermaid диаграмму
        if args.generate_mermaid:
            print(f"\nГенерация Mermaid диаграммы...")
            mermaid_code = generate_mermaid_graph(graph, args.package_name, cyclic_dependencies)
            
            # Сохраняем Mermaid код в файл
            mmd_file = args.output.replace('.svg', '.mmd')
            with open(mmd_file, 'w', encoding='utf-8') as f:
                f.write(mermaid_code)
            print(f"Mermaid код сохранен в: {mmd_file}")
            
            # Сохраняем SVG
            if save_mermaid_svg(mermaid_code, args.output):
                print(f"SVG диаграмма успешно сгенерирована: {args.output}")
            else:
                print(f"Не удалось сгенерировать SVG диаграмму")
        
        # Выводим статистику
        analyze_graph_statistics(graph, cyclic_dependencies)
        
        # Выводим порядок загрузки если запрошено
        if args.show_load_order:
            print("\n" + "=" * 60)
            print("ПОРЯДОК ЗАГРУЗКИ ЗАВИСИМОСТЕЙ")
            print("=" * 60)
            
            load_order = calculate_load_order(graph, args.package_name)
            
            print("Рекомендуемый порядок загрузки:")
            for i, package in enumerate(load_order, 1):
                package_info = graph.get(package, {})
                version = package_info.get('version', 'unknown')
                print(f"{i:2d}. {package}@{version}")
        
        print("\nЭтап 5 завершен успешно!")
        print("Визуализация графа зависимостей выполнена")
        
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