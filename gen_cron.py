lines = ['    - cron: "10 3 * * 1-5"   # 8:40 AM IST morning']
for ist_min in range(9 * 60 + 15, 15 * 60 + 15 + 1, 10):
    utc = ist_min - (5 * 60 + 30)
    h, m = divmod(utc, 60)
    ist_h, ist_m = divmod(ist_min, 60)
    lines.append(f'    - cron: "{m} {h} * * 1-5"   # {ist_h}:{ist_m:02d} IST')
print("\n".join(lines))