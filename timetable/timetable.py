import openpyxl
import pandas as pd

kurs_1_doc = openpyxl.load_workbook('Raspisanie_1_kurs_osen_2019.xlsm')
kurs_1 = kurs_1_doc.active

groups = {}  # список расписаний для групп


def within_range(bounds: tuple, cell: openpyxl.cell) -> bool:
    """
    Функция, определяющая, является ли клетка слитой или нет
    :param bounds:
    :param cell:
    :return: True, если merged клетка, иначе False
    """
    column_start, row_start, column_end, row_end = bounds
    row = cell.row
    if row_start <= row <= row_end:
        column = cell.column
        if column_start <= column <= column_end:
            return True
    return False


def get_value_merged(sheet: openpyxl.worksheet, cell: openpyxl.cell) -> any:
    """
    Функция, возвращающая значение, лежащее в клетке, вне зависимости от того,
    является ли клетка merged, или нет
    :param sheet:
    :param cell:
    :return: значение, лежащее в клетке
    """
    for merged in sheet.merged_cells:
        if within_range(merged.bounds, cell):
            return sheet.cell(merged.min_row, merged.min_col).value
    return cell.value


for j in range(3, kurs_1.max_column):  # смотрим на значения по столбцам
    name = kurs_1.cell(1, j).value  # номер группы
    if name in ['Дни', 'Часы']:  # если это не номер группы, то пропускаем столбец
        continue
    # иначе если столбец - это номер группы, то составляем для него расписание
    elif name is not None:
        # group - словарь с расписанием для группы
        group = dict(Понедельник={}, Вторник={}, Среда={}, Четверг={}, Пятница={}, Суббота={}, Воскресенье={})
        for k in range(2, kurs_1.max_row):  # проходимся по столбцу
            # если клетки относятся ко дню недели (не разделители)
            if get_value_merged(kurs_1, kurs_1.cell(k, 1)) in group.keys():
                # если это обычная клетка, а не слитая из нескольких, то записываем значение "время - пара"
                # (в том случае, если этого значения еще нет в расписании)
                day = get_value_merged(kurs_1, kurs_1.cell(k, 1))  # значение дня недели
                time = get_value_merged(kurs_1, kurs_1.cell(k, 2))  # клетка, в которой лежит значение времени
                pair = get_value_merged(kurs_1, kurs_1.cell(k, j))  # клетка, в которой лежит значение пары

                # рассматриваем только те клетки, для которых определено значение как пары, так и времени
                if (time, pair) != (None, None):
                    time = time.split()  # преобразуем время пары к формату hh:mm – hh:mm
                    if len(time[0][:-2]) == 1:
                        time[0] = '0' + time[0]
                    time = time[0][:-2] + ':' + time[0][-2:] + ' – ' + time[2][:-2] + ':' + time[2][-2:]
                    group[day][time] = pair

        group = pd.DataFrame(group)  # заменяем None на более красивые прочерки
        group.replace(to_replace=[None], value='–', inplace=True)
        groups[name] = group

print(groups)
