"""Fictional public NLU fixtures; never imports production hidden state."""
from core import digest

# label, unit, value phrases. Phrases are grammatical standalone nominal clauses.
DOMAINS = [
 ('procurement', 'S1-like', 'Согласование партии комплектующих', [
   ('PRICE', 'Цена', 'тыс. условных единиц', ['68 тысяч', '74 тысячи', '82 тысячи']),
   ('DELIVERY', 'Доставка', 'график', ['единая поставка в среду', 'две поставки по понедельникам', 'самовывоз в четверг']),
   ('PREPAY', 'Предоплата', 'доля', ['без предоплаты', 'аванс 20%', 'аванс 40%'])]),
 ('workload', 'S2-like', 'Распределение задач между участниками команды', [
   ('SCOPE', 'Объём', 'работы', ['только прототип', 'прототип и тесты', 'полный релиз']),
   ('DEADLINE', 'Срок', 'дней', ['три рабочих дня', 'шесть рабочих дней', 'девять рабочих дней']),
   ('HELP', 'Помощь', 'ресурс', ['без помощника', 'помощник на полдня', 'помощник на весь день']),
   ('DEFER_REPORT', 'Отчёт', 'график', ['без переноса отчёта', 'перенос отчёта на среду', 'перенос отчёта на пятницу'])]),
 ('logistics', 'synthetic', 'Маршрут перевозки оборудования', [
   ('ROUTE', 'Маршрут', 'вариант', ['прямой рейс', 'рейс через склад', 'сборный рейс']),
   ('WINDOW', 'Окно разгрузки', 'время', ['утреннее окно', 'дневное окно', 'вечернее окно']),
   ('INSURANCE', 'Страхование', 'покрытие', ['без страхования', 'базовое покрытие', 'полное покрытие'])]),
 ('project', 'synthetic', 'Объём и календарь разработки сайта', [
   ('FEATURES', 'Состав работ', 'объём', ['лендинг', 'каталог без оплаты', 'каталог с оплатой']),
   ('DATE', 'Срок сдачи', 'дата', ['до вторника включительно', 'до четверга включительно', 'не позже пятницы']),
   ('REVIEW', 'Правки', 'раунды', ['один раунд', 'два раунда', 'три раунда'])]),
 ('service', 'synthetic', 'Периодическое обслуживание оборудования', [
   ('VISITS', 'Выезды', 'частота', ['один выезд в месяц', 'два выезда в месяц', 'еженедельный выезд']),
   ('PARTS', 'Запчасти', 'порядок', ['запчасти заказчика', 'запчасти исполнителя', 'отдельный заказ запчастей']),
   ('TERM', 'Длительность', 'период', ['договор на квартал', 'договор на полгода', 'договор на год'])]),
 ('b2b_pricing', 'synthetic', 'Тариф поставки упаковочных материалов', [
   ('PRICE', 'Цена', 'руб. за единицу', ['46 рублей', '58 рублей', '72 рубля']),
   ('VOLUME', 'Тираж', 'единиц', ['600 единиц', '900 единиц', '1200 единиц']),
   ('PAYMENT', 'Оплата', 'порядок', ['оплата при получении', 'оплата через десять дней', 'оплата через двадцать дней'])]),
 ('hiring', 'synthetic', 'Условия работы вымышленной вакансии', [
   ('HOURS', 'Рабочая неделя', 'нагрузка', ['24 часа в неделю', '32 часа в неделю', '40 часов в неделю']),
   ('FORMAT', 'Формат', 'режим', ['полностью удалённо', 'два дня в офисе', 'четыре дня в офисе']),
   ('START', 'Выход на работу', 'срок', ['выход через неделю', 'выход через две недели', 'выход через месяц'])]),
 ('resources', 'synthetic', 'Распределение лабораторного оборудования', [
   ('SLOTS', 'Сеансы', 'число', ['два сеанса', 'четыре сеанса', 'шесть сеансов']),
   ('SHIFT', 'Смена', 'время', ['первая смена', 'вторая смена', 'ночная смена']),
   ('TECH', 'Техник', 'участие', ['без техника', 'техник на запуск', 'техник на всю смену'])]),
 ('support', 'synthetic', 'Параметры технической поддержки', [
   ('RESPONSE', 'Время ответа', 'часов', ['ответ за час', 'ответ за три часа', 'ответ за шесть часов']),
   ('COVERAGE', 'График поддержки', 'режим', ['только будни', 'будни и суббота', 'все дни недели']),
   ('CHANNEL', 'Канал связи', 'канал', ['чат', 'телефон', 'чат и телефон'])]),
 ('rent', 'synthetic', 'Коммерческие условия аренды помещения', [
   ('RENT', 'Арендная плата', 'тыс. в месяц', ['36 тысяч в месяц', '48 тысяч в месяц', '62 тысячи в месяц']),
   ('DURATION', 'Срок аренды', 'месяцев', ['аренда на четыре месяца', 'аренда на восемь месяцев', 'аренда на год']),
   ('DEPOSIT', 'Депозит', 'размер', ['без депозита', 'депозит за полмесяца', 'депозит за месяц'])]),
]

FACTS = {
 'procurement': ['склад принимает партии по предварительной записи', 'упаковка возвращается поставщику'],
 'workload': ['тестовый стенд доступен только утром', 'проверка релиза проводится отдельной командой'],
 'logistics': ['на складе есть погрузчик', 'пропуск оформляется до приезда'],
 'project': ['макеты переданы разработчику', 'контент готовит заказчик'],
 'service': ['журнал осмотров ведётся в электронном виде', 'вход на площадку согласуется заранее'],
 'b2b_pricing': ['макет упаковки уже утверждён', 'этикетки печатает заказчик'],
 'hiring': ['оборудование выдаёт работодатель', 'вводный курс проходит дистанционно'],
 'resources': ['лаборатория ведёт общий календарь сеансов', 'расходники выдаются перед сменой'],
 'support': ['заявки регистрируются в общем журнале', 'резервная линия проверяется каждую неделю'],
 'rent': ['в помещении есть отдельный счётчик', 'ключи передаются по акту'],
}


def make_contexts():
    registry = {}
    for domain_index, (domain, family, brief, specs) in enumerate(DOMAINS):
        for mode in ('descriptive', 'semi_opaque', 'opaque'):
            for state in ('plain', 'active', 'active_alt', 'active_third', 'no_arguments', 'no_price_topic'):
                cid = f'{domain}.{mode}.{state}'
                def ident(kind, i, hint):
                    if mode == 'descriptive':
                        return hint
                    if mode == 'semi_opaque':
                        return f'{kind}_{i + 1:02}'
                    return digest([cid, kind, i])[:12]
                issues = []
                for i, (iid, label, unit, phrases) in enumerate(specs):
                    issues.append(dict(id=ident('i', i, iid), label=label, unit=unit, ordered=False,
                                       values=[dict(id=ident(f'v{i}', j, f'{iid.lower()}_{j+1}'), label=p, quantity=None)
                                               for j, p in enumerate(phrases)]))
                topics = [dict(id=ident('t', i, f'discuss_{s[0].lower()}'), label=s[1]) for i, s in enumerate(specs)]
                topic_map = [t['id'] for t in topics]
                if state == 'no_price_topic':
                    # Test null even when PRICE is a valid issue. Other topics are still public.
                    topic_map[0] = None
                    topics = topics[1:]
                facts = [dict(id=ident('f', i, f'{domain}_known_{i+1}'), text=s[0].upper()+s[1:]+'.')
                         for i, s in enumerate(FACTS[domain])]
                args = [dict(claimId=ident('a', i, f'{domain}_reason_{i+1}'),
                             label=f'Учесть организацию: {specs[i][1].lower()}', supportingFactIds=[facts[i]['id']],
                             condition=[dict(kind='eq', issueId=issues[i]['id'], valueId=issues[i]['values'][1]['id'])])
                        for i in range(2)] if state != 'no_arguments' else []
                active = None
                if state.startswith('active'):
                    active_value = ('active', 'active_alt', 'active_third').index(state)
                    active = dict(id='2060-'+digest(cid)[:8]+'-'+digest(cid)[8:20], proposer='opponent',
                                  terms=[dict(issueId=issue['id'], valueId=issue['values'][active_value]['id']) for issue in issues],
                                  turnNumber=1, supersedesId=None)
                public = dict(revision=1, turnNumber=1,
                              player=dict(roleId='representative', label='Представитель', briefing='Обсудите открытые условия.'),
                              publicBrief=brief+'. Учебная вымышленная ситуация.', issues=issues, topics=topics,
                              knownFacts=facts, acknowledgementFactIds=[f['id'] for f in facts],
                              availableArguments=args, activeOffer=active)
                modes = ('descriptive', 'semi_opaque', 'opaque')
                state_group = ('active','active_alt','active_third') if state.startswith('active') else ('plain','no_arguments','no_price_topic')
                slot = modes.index(mode)*3+state_group.index(state)
                held_test = (domain_index+(4 if state.startswith('active') else 5))%9
                split = 'dev' if slot==domain_index%9 else 'internal_test' if slot==held_test else 'train'
                registry[cid] = dict(domainFamily=domain, scenarioFamily=family, identifierStyle=mode, split=split,
                                     topicByIssue=topic_map, publicContext=public)
    return registry
