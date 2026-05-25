"""
Internationalization module for SOCHIAUTOPARTS static site generator.

Contains ALL UI strings in both Russian (default) and English.
Content (posts, articles) is IDENTICAL for both ru and en — only UI labels/strings differ.
"""

STRINGS = {
    'ru': {
        # Navigation
        'nav_home': 'Главная',
        'nav_articles': 'Статьи',
        'nav_shop': 'Магазин',
        'nav_archive': 'Архив',
        'nav_contacts': 'Контакты',
        'nav_privacy': 'Конфиденциальность',

        # Hero section
        'hero_title': 'SOCHIAUTOPARTS',
        'hero_subtitle': 'Ежедневные новости, тест-драйвы и обзоры мирового автопрома.',
        'hero_cta': 'Подписаться',

        # Search
        'search_placeholder': 'Поиск...',
        'search_btn_title': 'Искать',
        'search_no_results': 'Ничего не найдено',

        # Posts
        'read_more': 'Читать далее',
        'in_telegram': 'В Telegram',
        'post_views': 'просмотры',
        'related_posts': 'Похожие материалы',
        'posts_count': '{count} публикаций',

        # Pagination
        'page': 'Страница',
        'prev': '← Назад',
        'next': 'Вперёд →',

        # Articles
        'articles_title': 'Статьи - Руководства по ремонту и обслуживанию автомобилей',
        'articles_subtitle': 'Подробные руководства по ремонту и обслуживанию популярных автомобилей. Полные инструкции, советы по техническому обслуживанию.',

        # Archive
        'archive_title': 'Архив публикаций',
        'archive_subtitle': 'Архив всех публикаций канала sochiautoparts в Telegram. Автоновости, обзоры, тест-драйвы и акции.',
        'archive_newer': '← Новее',
        'archive_older': 'Старее →',
        'archive_post_views': 'просмотры',
        'open_in_telegram': 'Открыть в Telegram',

        # Shop
        'shop_title': 'Магазин автозапчастей',
        'shop_subtitle': 'Большой выбор автозапчастей от 6 проверенных поставщиков. 95 165 товаров с доставкой по всей России.',
        'shop_search_placeholder': 'Поиск запчастей...',
        'shop_sort_popular': 'По популярности',
        'shop_sort_price_asc': 'Цена: по возрастанию',
        'shop_sort_price_desc': 'Цена: по убыванию',
        'shop_sort_name': 'По названию',
        'shop_empty': 'Товары не найдены',
        'shop_empty_reset': 'Сбросить фильтры',
        'shop_feature_delivery': 'Доставка по всей России',
        'shop_feature_verified': 'Проверенные поставщики',
        'shop_feature_prices': 'Лучшие цены',
        'shop_feature_guarantee': 'Гарантия качества',
        'shop_visit': 'Перейти в магазин',
        'shop_buy': 'Купить',

        # Product page
        'product_category': 'Категория',
        'product_vendor': 'Производитель',
        'product_price': 'Цена',
        'product_related': 'Похожие товары',

        # Privacy
        'privacy_title': 'Политика конфиденциальности и использования файлов Cookie',

        # Contacts
        'contacts_title': 'Контакты',
        'contacts_email': 'Электронная почта',
        'contacts_telegram': 'Telegram',
        'contacts_instagram': 'Instagram',

        # Cookie consent
        'cookie_text': 'Мы используем файлы cookie для улучшения работы сайта и анализа трафика.',
        'cookie_accept': 'Принять',
        'cookie_decline': 'Отклонить',
        'cookie_learn_more': 'Подробнее',

        # 404
        '404_title': 'Страница не найдена',
        '404_text': 'Запрашиваемая страница не существует.',
        '404_redirect': 'Через 8 секунд вы будете перенаправлены на главную.',

        # Footer
        'footer_rights': 'Все права защищены.',
        'footer_popular_tags': 'Популярные теги',

        # SEO
        'seo_block_title': 'О канале SOCHIAUTOPARTS',
        'seo_block_text': 'SOCHIAUTOPARTS — ваш источник мировых автоновостей, экспертных обзоров и тест-драйвов. Ежедневные публикации трендов глобального автопрома.',

        # Breadcrumbs
        'bc_home': 'Главная',
        'bc_articles': 'Статьи',
        'bc_archive': 'Архив',
        'bc_shop': 'Магазин',
        'bc_tag': 'Тег',
        'bc_product': 'Товар',
        'bc_category': 'Категория',

        # Language
        'lang_ru': 'RU',
        'lang_en': 'EN',

        # Theme
        'theme_light': '☀️',
        'theme_dark': '🌙',

        # Ads/Admitad
        'ads_title': 'Рекомендуем',
        'ads_visit': 'Перейти',
        'ads_all': 'Все предложения',
        'ads_parts': 'Запчасти',
        'ads_insurance': 'Страхование',
        'ads_tires': 'Шины',
        'ads_check': 'Проверка авто',
        'ads_rental': 'Аренда',
        'ads_tools': 'Инструменты',
        'ads_coupons': 'Промокоды',
        'ads_other': 'Прочее',
        'ads_legal': 'Реклама',

        # Manifest
        'manifest_name': 'SOCHIAUTOPARTS',
        'manifest_short_name': 'SAP',
    },
    'en': {
        # Navigation
        'nav_home': 'Home',
        'nav_articles': 'Articles',
        'nav_shop': 'Shop',
        'nav_archive': 'Archive',
        'nav_contacts': 'Contacts',
        'nav_privacy': 'Privacy',

        # Hero section
        'hero_title': 'SOCHIAUTOPARTS',
        'hero_subtitle': 'Daily news, test drives and reviews of the global automotive industry.',
        'hero_cta': 'Subscribe',

        # Search
        'search_placeholder': 'Search...',
        'search_btn_title': 'Search',
        'search_no_results': 'No results found',

        # Posts
        'read_more': 'Read more',
        'in_telegram': 'In Telegram',
        'post_views': 'views',
        'related_posts': 'Related Posts',
        'posts_count': '{count} posts',

        # Pagination
        'page': 'Page',
        'prev': '← Previous',
        'next': 'Next →',

        # Articles
        'articles_title': 'Articles - Car Repair and Maintenance Guides',
        'articles_subtitle': 'Detailed repair and maintenance guides for popular cars. Complete instructions and service tips.',

        # Archive
        'archive_title': 'Publications Archive',
        'archive_subtitle': 'Archive of all sochiautoparts Telegram channel publications. Auto news, reviews, test drives and promos.',
        'archive_newer': '← Newer',
        'archive_older': 'Older →',
        'archive_post_views': 'views',
        'open_in_telegram': 'Open in Telegram',

        # Shop
        'shop_title': 'Auto Parts Shop',
        'shop_subtitle': 'Large selection of auto parts from 6 verified suppliers. 95,165 products with delivery across Russia.',
        'shop_search_placeholder': 'Search parts...',
        'shop_sort_popular': 'By popularity',
        'shop_sort_price_asc': 'Price: low to high',
        'shop_sort_price_desc': 'Price: high to low',
        'shop_sort_name': 'By name',
        'shop_empty': 'No products found',
        'shop_empty_reset': 'Reset filters',
        'shop_feature_delivery': 'Delivery across Russia',
        'shop_feature_verified': 'Verified suppliers',
        'shop_feature_prices': 'Best prices',
        'shop_feature_guarantee': 'Quality guarantee',
        'shop_visit': 'Visit Shop',
        'shop_buy': 'Buy',

        # Product page
        'product_category': 'Category',
        'product_vendor': 'Vendor',
        'product_price': 'Price',
        'product_related': 'Related Products',

        # Privacy
        'privacy_title': 'Privacy Policy & Cookie Use',

        # Contacts
        'contacts_title': 'Contacts',
        'contacts_email': 'Email',
        'contacts_telegram': 'Telegram',
        'contacts_instagram': 'Instagram',

        # Cookie consent
        'cookie_text': 'We use cookies to improve your experience and analyze traffic.',
        'cookie_accept': 'Accept',
        'cookie_decline': 'Decline',
        'cookie_learn_more': 'Learn more',

        # 404
        '404_title': 'Page Not Found',
        '404_text': 'The requested page does not exist.',
        '404_redirect': 'You will be redirected to the homepage in 8 seconds.',

        # Footer
        'footer_rights': 'All rights reserved.',
        'footer_popular_tags': 'Popular Tags',

        # SEO
        'seo_block_title': 'About SOCHIAUTOPARTS',
        'seo_block_text': 'SOCHIAUTOPARTS — your source for global automotive news, expert reviews and test drives. Daily publications of worldwide auto industry trends.',

        # Breadcrumbs
        'bc_home': 'Home',
        'bc_articles': 'Articles',
        'bc_archive': 'Archive',
        'bc_shop': 'Shop',
        'bc_tag': 'Tag',
        'bc_product': 'Product',
        'bc_category': 'Category',

        # Language
        'lang_ru': 'RU',
        'lang_en': 'EN',

        # Theme
        'theme_light': '☀️',
        'theme_dark': '🌙',

        # Ads/Admitad
        'ads_title': 'Recommended',
        'ads_visit': 'Visit',
        'ads_all': 'All offers',
        'ads_parts': 'Parts',
        'ads_insurance': 'Insurance',
        'ads_tires': 'Tires',
        'ads_check': 'Vehicle Check',
        'ads_rental': 'Rental',
        'ads_tools': 'Tools',
        'ads_coupons': 'Coupons',
        'ads_other': 'Other',
        'ads_legal': 'Advertisement',

        # Manifest
        'manifest_name': 'SOCHIAUTOPARTS',
        'manifest_short_name': 'SAP',
    }
}


def t(key, lang='ru', **kwargs):
    """Get translated string by key and language.

    Args:
        key: String key to look up in the STRINGS dictionary.
        lang: Language code ('ru' or 'en'). Defaults to 'ru'.
        **kwargs: Optional format keyword arguments (e.g. count=42 for '{count} публикаций').

    Returns:
        The translated string, with any format arguments applied.
        Falls back to Russian if the language is not found,
        falls back to the key itself if the key is not found.
    """
    strings = STRINGS.get(lang, STRINGS['ru'])
    value = strings.get(key, STRINGS['ru'].get(key, key))
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value
