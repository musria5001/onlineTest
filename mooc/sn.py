from mooc.models import Number
import xlrd

Num = Number.objects.all()
name = '3618571-3621610'
filename = name + '.xls'
xls = xlrd.open_workbook(filename=filename)
sheet = xls.sheet_by_name(name)
count = 0
for i in range(sheet.nrows):
    ming_ma = sheet.cell(i,0).value
    an_ma = sheet.cell(i,1).value
    try:
        if Number.objects.filter(ming_ma=ming_ma):
            print("该激活码已被导入:明码：{}，暗码：{}".format(ming_ma,an_ma))
            continue
        num = Number(ming_ma=ming_ma, an_ma=an_ma)
        num.save()
        count += 1
    except:
        print("该信息有误:明码：{}，暗码：{}".format(ming_ma,an_ma))
else:
    print("共计导入{}条激活码信息。".format(count))
