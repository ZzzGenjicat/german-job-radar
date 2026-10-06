"""One public grouping and stable batch-wide numbers for UI and export."""
import copy


def display_group(classification):
    return 'excluded' if classification == 'excluded' else 'review'


def verification_label(job):
    if job.get('classification') == 'excluded':
        return '触发排除规则'
    if job.get('classification') in ('recommended', 'previous'):
        return '自动核验未发现缺口；仍需人工筛查'
    return '仍有核验缺口'


def numbered_jobs(jobs):
    result = copy.deepcopy(jobs)
    for number, job in enumerate(result, 1):
        job['number'] = number
        job['display_group'] = display_group(job.get('classification'))
        job['verification_label'] = verification_label(job)
    return result
