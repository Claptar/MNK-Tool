import pickle

import openpyxl
import timetable


def timetable_by_course(file_name):
    """
    Функция для считывания расписания курса из файла .xslx с несколькими листами (sheets)
    :param file_name: имя файла с расписанием
    :return: добавляет в список groups pd.DataFrame с расписанием курса
    """
    course = openpyxl.load_workbook(file_name)
    for sheet in course.worksheets:
        timetable.get_timetable(sheet)


# Считываем расписание из экселевских файлов в базу данных
# меняем их на новые в каждом семе, при замене, возможно, нужно внести правки в функцию timetable.get_timetable()
def insert_timetables_to_database(first_course, last_course, name_of_file: str):
    for i in range(first_course, last_course + 1):
        timetable_by_course('{}-{}.xlsx'.format(i, name_of_file))


if __name__ == '__main__':
    insert_timetables_to_database(1, 5, 'kurs-vesna-2019_2020')
    with open('blank_timetable.pickle', 'rb') as handle:
        alumni = pickle.load(handle)
    timetable.insert_update_group_timetable(
        'ALUMNI',
        alumni
    )
