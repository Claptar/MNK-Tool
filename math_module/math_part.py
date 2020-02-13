# -*- coding: utf-8 -*-
import os

import math
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sympy as sp

LABEL_X = ''
LABEL_Y = ''
TITLE = ''
BOT_PLOT = False
PATH = os.path.abspath('')
ERROR_BAR = False
LABEL = []
ERRORS = [0, 0]


def data_conv(data_file):
    """
    Программа, которая конвертирует данные из таблицы в массив [x,y]
    :param data_file: название файла
    :return: [x,y]
    """
    global LABEL
    dataset = pd.read_excel(data_file)
    LABEL = dataset.columns
    d = np.array(dataset)
    x = d[:, 0]
    y = d[:, 1]
    return [x, y]


def plt_const(x, y):
    """
    Функция рассчитывает по МНК коэффициенты прямой по полученным координатам точек. Так же рассчитывает их погрешности.
    :param x: Массив абсцисс точек
    :param y: Массив оридинат точек
    :return: [значение углового коэфф a, значение коэфф b, значение погрешности a, значение погрешности b]
    """
    av_x = np.sum(x)/len(x)
    av_y = np.sum(y)/len(y)
    sigmas_x = np.sum(x*x)/len(x) - (np.sum(x)/len(x))**2
    sigmas_y = np.sum(y*y)/len(y) - (np.sum(y)/len(y))**2
    r = np.sum(x*y)/len(x) - av_x*av_y
    a = r/sigmas_x
    b = av_y - a*av_x
    try:
        d_a = 2 * math.sqrt((sigmas_y / sigmas_x - a ** 2) / (len(x) - 2))
        d_b = d_a * math.sqrt(sigmas_x + av_x ** 2)
    except Exception as e:
        print(e)
        d_a = 'error'
        d_b = 'error'
    return [a, b, d_a, d_b]


def const_dev(x, y):
    """
    Функция рассчитывает погрешности коэффициентов прямой по полученным координатам точек
    :param x: Массив абсцисс точек
    :param y: Массив оридинат точек
    :return:
    """
    return [plt_const(x, y)[2], plt_const(x, y)[3]]


def plots_drawer(data_file, tit, xerr, yerr, mnk):
    """
    Функция считывает данные из таблицы и строит графики с МНК по этим данным
    :param data_file: Название файла с данными
    :param tit: название графика
    :param xerr: погрешность по х
    :param yerr: погрешность по y
    :param mnk: type Bool, При True строится прямая мнк
    :return:
    """
    fig, ax = plt.subplots()
    dataset = pd.read_excel(data_file)
    d = np.array(dataset)[0:, :]
    a = []
    b = []
    x = []
    y = []
    x_ = []
    for i in range(0, len(d[0, :] - 1) // 2 * 2, 2):
        r = plt_const(d[:, i], d[:, i + 1])
        x.append(d[:, i])
        y.append(d[:, i + 1])
        a.append(r[0])
        b.append(r[1])
    if mnk:
        for i in range(0, len(x)):
            if xerr != 0 or yerr != 0:
                ax.errorbar(x[i], y[i], xerr=xerr, yerr=yerr, fmt='k+')
    for i in range(0, len(x)):
        delta = (max(x[i]) - min(x[i]))/len(x[i])
        x_.append([min(x[i]) - delta, max(x[i]) + delta])
        ax.plot(x[i], y[i], 'o')
    if mnk:
        for i in range(0, len(x)):
            ax.plot(np.array(x_[i]), a[i]*(np.array(x_[i])) + b[i], 'r')
    ax.set_xlabel(dataset.columns[0])
    ax.set_ylabel(dataset.columns[1])
    lab = np.array(dataset)[0, :]
    lab1 = []
    for i in range(0, len(lab)):
        if type(lab[i]) == str:
            lab1.append(lab[i])
    ax.legend(lab1)
    ax.set_title(tit)
    ax.grid(True)
    # Находим координаты углов графика
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    # Добавляем горизонтальную стрелку на ось
    ax.annotate("",
                xy=(xmax, ymin), xycoords='data',
                xytext=(xmin, ymin), textcoords='data',
                arrowprops=dict(facecolor='black',
                                shrink=0,
                                width=0.1,
                                headwidth=6,
                                headlength=10,
                                connectionstyle="arc3"),
                )
    # Добавляем вертикальную стрелку на ось
    ax.annotate("",
                xy=(xmin, ymax), xycoords='data',
                xytext=(xmin, ymin), textcoords='data',
                arrowprops=dict(facecolor='black',
                                shrink=0,
                                width=0.1,
                                headwidth=6,
                                headlength=10,
                                connectionstyle="arc3"),
                )
    if BOT_PLOT:
        plt.savefig('plot.pdf')
        plt.savefig('plot.png')
    else:
        plt.show()
    plt.clf()


def mnk_calc(data_file):
    """
    Функция считывает данные из таблицы и возвращает коэффициенты и погрешности
    :param data_file: Название файла с данными
    :return: [a - коэф. прямой, b - коэф. прямой, погрешность а, погрешность b]
    """
    dataset = pd.read_excel(data_file)
    d = np.array(dataset)
    a = []
    b = []
    x = []
    y = []
    d_a = []
    d_b = []
    for i in range(0, len(d[1, :] - 1), 2):
        r = plt_const(d[:, i], d[:, i + 1])
        x.append(d[:, i])
        y.append(d[:, i + 1])
        a.append(r[0])
        b.append(r[1])
        d_a.append(r[2])
        d_b.append(r[3])

    return [a, b, d_a, d_b]


def error_calc(equation, var_list, point_list, error_list):
    """

    :param equation: формула в формате, приемлемом для python
    :param var_list: список переменных
    :param point_list: список значений переменных в точке соответсвенно со списком переменных
    :param error_list: список погрешностей для каждой переменной соответсвенно со списком переменных
    :return: погрешность
    """
    sigma = 0  # Объявляем переменную
    for number in range(len(var_list)):
        elem = sp.Symbol(var_list[number])  # переводит символ в приемлемый формат для дифференцирования
        der = sp.diff(equation, elem)  # дифференцируем выражение equation по переменной elem
        for score in range(len(point_list)):  # задаем каждую переменную, чтобы подставить ее значение
            der = sp.lambdify(var_list[score], der, 'numpy')  # говорим, что функция будет конкретной переменной
            der = der(point_list[score])  # задаем функцию в строчном виде
        sigma += error_list[number] ** 2 * der ** 2  # считем погрешность

    return sigma


plots_drawer('Example.xlsx', '', 0, 0, False)
