from datetime import date, datetime

purchase_date = date.today().strftime("%b-%d-%Y")
print(purchase_date)

purchase_time = datetime.now().strftime("%H:%M:%S")
print(purchase_time)
