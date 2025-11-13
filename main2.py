import argparse
import sys
import os

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
        
        # ВЫВОД РЕЗУЛЬТАТОВ - ТРЕБОВАНИЕ ЭТАПА 1
        
        print("=" * 50)
        print("НАСТРОЙКИ ПРОГРАММЫ")
        print("=" * 50)
        
        # Выводим все параметры в формате ключ-значение
        print(f"package-name: {args.package_name}")
        print(f"repo-url: {args.repo_url}")
        print(f"test-repo: {args.test_repo}")
        print(f"version: {args.version}")
        print(f"output: {args.output}")
        print(f"show-tree: {args.show_tree}")
        print(f"filter: {args.filter}")
        
        print("=" * 50)
        print("Конфигурация успешно загружена!")
        print("На данном этапе программа только показывает настройки")
        print("Анализ зависимостей будет реализован в следующих этапах")
        
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