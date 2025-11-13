import argparse
import sys
import os
import json
import urllib.request
import urllib.error

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
        
        # ЭТАП 2: СБОР ДАННЫХ О ЗАВИСИМОСТЯХ
        
        print("=" * 50)
        print("ЭТАП 2: СБОР ДАННЫХ О ЗАВИСИМОСТЯХ")
        print("=" * 50)
        
        # Получаем информацию о пакете
        print(f"Получение информации о пакете '{args.package_name}' версии '{args.version}'...")
        package_data = fetch_package_info(args.package_name, args.repo_url, args.version)
        
        # Получаем информацию о конкретной версии
        version_info = get_package_version_info(package_data, args.version)
        
        # Извлекаем прямые зависимости
        dependencies = extract_dependencies(version_info)
        
        # ВЫВОД РЕЗУЛЬТАТОВ - ТРЕБОВАНИЕ ЭТАПА 2
        print(f"\nПРЯМЫЕ ЗАВИСИМОСТИ ПАКЕТА '{args.package_name}@{version_info.get('version', 'unknown')}':")
        print("-" * 60)
        
        if not dependencies:
            print("Прямые зависимости не найдены")
        else:
            for dep_name, dep_version in dependencies.items():
                # Применяем фильтр если указан
                if args.filter and args.filter not in dep_name:
                    continue
                print(f"  {dep_name}: {dep_version}")
        
        print(f"\nВсего прямых зависимостей: {len(dependencies)}")
        
        # Выводим общую информацию о пакете
        print("\n" + "=" * 50)
        print("ОБЩАЯ ИНФОРМАЦИЯ О ПАКЕТЕ:")
        print("=" * 50)
        print(f"Имя пакета: {args.package_name}")
        print(f"Версия: {version_info.get('version', 'unknown')}")
        print(f"Описание: {version_info.get('description', 'не указано')}")
        print(f"Репоизиторий: {args.repo_url}")
        
        print("\nЭтап 2 завершен успешно!")
        print("Данные о зависимостях получены и готовы для дальнейшего анализа")
        
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