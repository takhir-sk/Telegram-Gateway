import os

# 1. Расширения, которые мы собираем
ALLOWED_EXTENSIONS = {'.py', '.js', '.html', '.css', '.txt', '.md', '.yaml', '.yml'}

# 2. Важные файлы без расширений
ALLOWED_FILES = {'Dockerfile', 'requirements.txt', '.dockerignore', '.gitignore'}

# 3. Безопасность: список запрещенных файлов
FORBIDDEN_FILES = {'.env', 'secrets.txt', 'config_private.yaml'}

# 4. Папки, которые мы полностью пропускаем
IGNORE_DIRS = {
    '__pycache__', '.git', 'node_modules', 'venv', 'env', 
    '.idea', '.vscode', 'build', 'dist'
}

def collect_project_code(output_file='project_summary.md'):
    ignored_files_found = []
    
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for root, dirs, files in os.walk('.'):
            # Фильтруем папки
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                # Если файл — это сам отчет, пропускаем его
                if file == output_file:
                    continue
                    
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1]
                
                # Проверка на безопасность (черный список)
                if file in FORBIDDEN_FILES:
                    ignored_files_found.append(file_path)
                    continue
                
                # Условие сбора
                if ext in ALLOWED_EXTENSIONS or file in ALLOWED_FILES:
                    f_out.write(f"\n--- START OF FILE: {file_path} ---\n")
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f_in:
                            f_out.write(f_in.read())
                    except Exception as e:
                        f_out.write(f"[Ошибка чтения файла: {e}]\n")
                    f_out.write(f"\n--- END OF FILE: {file_path} ---\n")

        # Запись в конце документа о пропущенных файлах
        f_out.write("\n\n--- SECURITY & IGNORE SUMMARY ---\n")
        if ignored_files_found:
            f_out.write("Следующие файлы были ПРОПУЩЕНЫ в целях безопасности или согласно списку исключений:\n")
            for ignored in ignored_files_found:
                f_out.write(f"- {ignored}\n")
        else:
            f_out.write("Исключенных (FORBIDDEN_FILES) файлов в проекте не обнаружено.\n")
        f_out.write("--- END OF SUMMARY ---\n")

    print(f"Готово! Сборка завершена в {output_file}.")
    if ignored_files_found:
        print(f"Внимание: {len(ignored_files_found)} файла(ов) были исключены из соображений безопасности.")

if __name__ == "__main__":
    collect_project_code()