"""Safe UTF-8 CSV export for the currently displayed job list."""
import csv
import io
from .presentation import display_group, verification_label


HEADERS=('序号','分类','岗位','公司','地点','发布时间','日期精度','来源','实际命中词','匹配理由','核验或排除理由','岗位链接','申请链接')
HEADERS = HEADERS + ('核验状态',)
LABELS={'review':'待人工筛查','excluded':'已排除'}


def _cell(value):
    if isinstance(value,list):value='；'.join(str(x) for x in value)
    value=str(value or '').replace('\x00','')
    return "'"+value if value.lstrip()[:1] in ('=','+','-','@') else value


def build_csv(jobs):
    output=io.StringIO(newline='');writer=csv.writer(output)
    writer.writerow(('德国岗位雷达（只作为建议）',))
    writer.writerow(HEADERS)
    for number,job in enumerate(jobs,1):
        matches='；'.join(f"{x.get('label','')}：{x.get('reason','')}" for x in job.get('matches',[]))
        writer.writerow([_cell(x) for x in (
            job.get('number',number),LABELS[display_group(job.get('classification'))],
            job.get('title'),job.get('company'),job.get('location'),job.get('posted'),
            job.get('date_precision'),job.get('source'),job.get('search_terms',[]),matches,
            job.get('reasons',[]),job.get('url'),job.get('apply_url'), verification_label(job))])
    return '\ufeff'+output.getvalue()
