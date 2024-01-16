import telebot
from telebot import types
import threading
import sqlite3

# Инициализация бота
API_TOKEN = '5682413230:AAGBUiBe6NVSSl_l8vzQI9dMJ3LM1PEPSCs'
bot = telebot.TeleBot(API_TOKEN)

# Создаем блокировку для синхронизации доступа к базе данных
db_lock = threading.Lock()

# Функция для получения категорий
def get_categories():
    query = 'SELECT name FROM categories'
    with sqlite3.connect('recipes.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        categories = cursor.fetchall()
    return [category[0] for category in categories]

# Функция для выполнения запроса в базе данных
def execute_query(query, params=None, fetchall=False):
    with sqlite3.connect('recipes.db') as conn:
        cursor = conn.cursor()

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetchall:
            result = cursor.fetchall()
        else:
            result = cursor.fetchone()

    return result

# Функция для получения рецептов по категории
def get_recipes_by_category(category_name):
    query = '''
        SELECT title FROM recipes
        JOIN categories ON recipes.category_id = categories.id
        WHERE categories.name = ?
    '''
    recipes = execute_query(query, (category_name,), fetchall=True)
    return [recipe[0] for recipe in recipes]

# Функция для получения ID категории по её имени
def get_category_id(category_name):
    query = 'SELECT id FROM categories WHERE name = ?'
    result = execute_query(query, (category_name,))
    return result[0] if result else None

# Функция для получения деталей рецепта по его названию
def get_recipe_details_by_title(recipe_title):
    query = '''
        SELECT ingredients, instructions FROM recipes
        WHERE title = ?
    '''
    result = execute_query(query, (recipe_title,), fetchall=False)
    return result

# Обработчик команды /start и создание кнопки "Добавить рецепт"
@bot.message_handler(commands=['start'])
def handle_start(message):
    categories = get_categories()
    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [types.KeyboardButton(category) for category in categories]
    markup.add(*buttons, types.KeyboardButton("Добавить рецепт"))
    bot.send_message(message.chat.id, "Выберите категорию или добавьте свой рецепт.\n\n"
                                      "/help - получить подсказку\n"
                     , reply_markup=markup)

# Обработчик кнопок с категориями и кнопки "Добавить рецепт"
@bot.message_handler(func=lambda message: message.text in get_categories() or message.text == "Добавить рецепт")
def handle_categories(message):
    if message.text == "Добавить рецепт":
        # Вызываем функцию для добавления рецепта
        add_recipe_start(message)
    else:
        # Обрабатываем выбранную категорию как раньше
        category_name = message.text
        recipes = get_recipes_by_category(category_name)
        response = f"Рецепты в категории '{category_name}':\n"
        response += "\n".join([recipe for recipe in recipes])
        bot.send_message(message.chat.id, response)

# Функция для начала процесса добавления рецепта
def add_recipe_start(message):
    bot.send_message(message.chat.id, "Введите название рецепта:")

    # Регистрируем следующий шаг для получения названия рецепта
    bot.register_next_step_handler(message, add_recipe_details)

# Функция для получения деталей рецепта и выбора категории
def add_recipe_details(message):
    # Получаем название рецепта
    recipe_title = message.text

    # Отправляем запрос о введении ингредиентов
    bot.send_message(message.chat.id, "Введите ингредиенты для рецепта, разделяя их запятой:")

    # Регистрируем следующий шаг для получения ингредиентов
    bot.register_next_step_handler(message, add_recipe_ingredients, recipe_title)

# Функция для получения ингредиентов и перехода к инструкциям
def add_recipe_ingredients(message, recipe_title):
    # Получаем ингредиенты из текста сообщения
    ingredients = message.text

    # Отправляем запрос о введении инструкций
    bot.send_message(message.chat.id, "Введите инструкции по приготовлению рецепта:")

    # Регистрируем следующий шаг для получения инструкций
    bot.register_next_step_handler(message, add_recipe_instructions, recipe_title, ingredients)

# Функция для получения инструкций и выбора категории
def add_recipe_instructions(message, recipe_title, ingredients):
    # Получаем инструкции из текста сообщения
    instructions = message.text

    # Получаем список существующих категорий
    categories = get_categories()

    # Создаем клавиатуру с вариантами категорий
    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [types.KeyboardButton(category) for category in categories]
    markup.add(*buttons)

    # Отправляем сообщение с просьбой выбрать категорию
    bot.send_message(message.chat.id, "Выберите категорию для добавления рецепта:", reply_markup=markup)

    # Регистрируем следующий шаг для получения категории
    bot.register_next_step_handler(message, add_recipe_category, recipe_title, ingredients, instructions)

# Функция для получения категории и сохранения рецепта в базу данных
def add_recipe_category(message, recipe_title, ingredients, instructions):
    # Получаем выбранную категорию из текста сообщения
    chosen_category = message.text

    # Проверяем, что выбранная категория среди существующих
    if chosen_category not in get_categories():
        bot.send_message(message.chat.id, "Выберите категорию из списка.")
        return

    # Сохраняем рецепт в базу данных
    with db_lock:
        category_id = get_category_id(chosen_category)
        execute_query('INSERT INTO recipes (title, category_id, ingredients, instructions) VALUES (?, ?, ?, ?)',
                      (recipe_title, category_id, ingredients, instructions))

    bot.send_message(message.chat.id, f"Рецепт '{recipe_title}' успешно добавлен в категорию '{chosen_category}'!")

# Обработчик команды /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = (
        "Привет! Я бот для рецептов. Вот как вы можете использовать меня:\n\n"
        "Для добавления своего рецепта, нажмите кнопку Добавить рецепт, далее следуйте подсказкам бота\n"
        "Для получения сохраненного рецепта, выберете категорию и введите наименование блюда"
    )
    bot.send_message(message.chat.id, help_text)

# Обработчик для просмотра ингредиентов и способа приготовления рецепта
@bot.message_handler(func=lambda message: True)
def handle_recipe_view(message):
    # Получаем детали рецепта по его названию
    recipe_title = message.text
    details = get_recipe_details_by_title(recipe_title)

    # Проверяем, есть ли детали рецепта
    if details:
        ingredients, instructions = details
        response = f"Ингредиенты для рецепта '{recipe_title}':\n{ingredients}\n\nИнструкции:\n{instructions}"
    else:
        response = f"Рецепт с названием '{recipe_title}' не найден."

    bot.send_message(message.chat.id, response)

# Запуск бота
if __name__ == "__main__":
    bot.polling(none_stop=True)
