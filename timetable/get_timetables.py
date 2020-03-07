import openpyxl
import timetable
import pickle

groups = [[] for i in range(5)]  # список расписаний для каждого курса


# считываем расписания из экселевских файлов
# меняем их на новые в каждом семе, при замене, возмножно, нужно внести правки в функция timetable.get_timetable()
def timetable_by_kurs(file_name, course):
    kurs = openpyxl.load_workbook(file_name)
    for i, sheet in enumerate(kurs.worksheets):
        if i == 0:
            groups[course].append(timetable.get_timetable(sheet))
        else:
            groups[course][0].update(timetable.get_timetable(sheet))


for i in range(5):
    timetable_by_kurs('{}-kurs-vesna-2019_2020.xlsx'.format(i + 1), i)

for i in range(len(groups)):  # запись расписаний в удобный для хранения формат .pickle
    with open('{}_kurs.pickle'.format(i + 1), 'wb') as handle:
        pickle.dump(groups[i][0], handle, protocol=pickle.HIGHEST_PROTOCOL)
