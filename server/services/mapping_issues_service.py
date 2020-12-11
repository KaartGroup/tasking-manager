from server.models.postgis.mapping_issues import MappingIssueCategory
from server.models.postgis.task import TaskMappingIssue, TaskHistory, Task
from server.models.postgis.user import User
from server.models.postgis.project import Project
from server.models.postgis.statuses import TaskStatus
from server.models.dtos.mapping_issues_dto import MappingIssueCategoryDTO
from server.models.dtos.stats_dto import ProjectContributionsDTO
from server.services.stats_service import StatsService
from copy import deepcopy
import numpy as np

class MappingIssueCategoryService:

    @staticmethod
    def get_mapping_issue_category(category_id: int) -> MappingIssueCategory:
        """
        Get MappingIssueCategory from DB
        :raises: NotFound
        """
        category = MappingIssueCategory.get_by_id(category_id)

        if category is None:
            raise NotFound()

        return category

    @staticmethod
    def get_mapping_issue_category_as_dto(category_id: int) -> MappingIssueCategoryDTO:
        """ Get MappingIssueCategory from DB """
        category = MappingIssueCategoryService.get_mapping_issue_category(category_id)
        return category.as_dto()

    @staticmethod
    def create_mapping_issue_category(category_dto: MappingIssueCategoryDTO) -> int:
        """ Create MappingIssueCategory in DB """
        new_mapping_issue_category_id = MappingIssueCategory.create_from_dto(category_dto)
        return new_mapping_issue_category_id

    @staticmethod
    def update_mapping_issue_category(category_dto: MappingIssueCategoryDTO) -> MappingIssueCategoryDTO:
        """ Create MappingIssueCategory in DB """
        category = MappingIssueCategoryService.get_mapping_issue_category(category_dto.category_id)
        category.update_category(category_dto)
        return category.as_dto()

    @staticmethod
    def delete_mapping_issue_category(category_id: int):
        """ Delete specified license"""
        category = MappingIssueCategoryService.get_mapping_issue_category(category_id)
        category.delete()

    @staticmethod
    def get_all_mapping_issue_categories(include_archived):
        """ Get all mapping issue categories"""
        return MappingIssueCategory.get_all_categories(include_archived)


class MappingIssueExporter:

    def get_mapping_issues(self, project_id: int, detailedView: str):
        """
        Returns a csv string of all mapping issues associated with the given project summed and sorted by user
        raises: NotFound
        """
        detailed = False
        if (detailedView == "true"):
            detailed = True

        #user_dict {str username : {int task (taskId) : {str issue : str issue_count}}}
        #project_users is a list of users on the project with no duplicates
        #int num_validated_tasks
        #tasks_as_tasks_dict {int taskId : task}
        user_dict, project_users, num_validated_tasks, tasks_as_tasks_dict = MappingIssueExporter.compile_validated_tasks_by_user(project_id)

        #data_table {str user : numpy array of user issue totals}
        #category_index_dict {str issue : int issueId}
        #category_names_dict {int issueId : str issue}
        #max_category_index: int, max issueId
        #totals: numpy array of project issue totals
        data_table, category_index_dict, category_names_dict, max_category_index, totals = MappingIssueExporter.build_issue_totals_table(user_dict, project_users)

        #Format

        #Basic
        #    , issue, issue, issue, ...
        #user, count, count, count, ...
        #totals  ...

        #Detailed
        #  User  , taskID:validated by, issues......
        #        ,  id : validator    ,  count   ,  count   ,  count  ... 
        #        ,  id : validator    ,  count   ,  count   ,  count  ... 
        #user totals ...

        #grand totals at the bottom


        """ Build the csv string """
        project_contrib_dto = StatsService.get_user_contributions(project_id)

        all_rows = []
        issue_names_row = []
        if (detailed):
           issue_names_row.append('Username (tasks mapped)')
           issue_names_row.append('taskId: ValidatedBy')
        else:
            issue_names_row.append('Username (tasks mapped)')

        possible_indices = category_names_dict.keys()
        for i in range(1, max_category_index + 1):  #category id is the category's index. Category ids start at 1
            if (i in possible_indices):
                issue_names_row.append(category_names_dict[i])
            else:
                issue_names_row.append('')

        all_rows.append(','.join(issue_names_row))

        for user in project_users:
            row = []

            if (detailed):
                row.append('')
                i = 0
                for task in user_dict[user]:
                    validator = User.get_by_id(self, tasks_as_tasks_dict[task].validated_by).username

                    single_task_row = []
                    if (i == 0):
                        single_task_row.append(user)
                    else:
                        single_task_row.append('')
                    single_task_row.append(str(task) + ': ' + validator)
                    single_task_row_issue_counts = np.zeros(max_category_index + 1, dtype='i')
                    for issue in user_dict[user][task]:
                        category_index = category_index_dict[issue]
                        single_task_row_issue_counts[category_index] = user_dict[user][task][issue]

                    for issue_count in single_task_row_issue_counts:
                        single_task_row.append(str(issue_count))
                    single_task_row.pop(2)
                    all_rows.append(",".join(single_task_row))

                    i += 1

            num_mapped_tasks = -1
            for user_contrib in project_contrib_dto.user_contributions:
                if (user_contrib.username == user):
                    num_mapped_tasks = user_contrib.mapped
                    break

            row.append(user + ' (' + str(num_mapped_tasks) + ')')

            for issue_count in data_table[user]:
                row.append(str(issue_count))
            row.pop(1)

            if (detailed):
                row[1] = ''
                row[0] = user + ' totals (' + str(num_mapped_tasks) + ')'

            all_rows.append(','.join(row))
            if (detailed):
                all_rows[-1] = all_rows[-1] + '\n'

        totals_row = ['Project Totals']
        for value in totals:
            totals_row.append(str(value))
        if (not detailed):
            totals_row.pop(1)
        else:
            totals_row[1] = ''

        all_rows.append(','.join(totals_row))

        csv_string = '\n'.join(all_rows)
        #print(csv_string)

        return csv_string


    @staticmethod
    def compile_validated_tasks_by_user(project_id: int):
        all_project_tasks = Task.get_all_tasks(project_id)
        validated_tasks = []
        project_users = []
        for task in all_project_tasks:
            if (task.task_status == TaskStatus.VALIDATED.value):
                validated_tasks.append(task)
                if (task.mapper.username in project_users):
                    continue
                else:
                    project_users.append(task.mapper.username)
            else:
                continue

        def mapper_username(task):
            return task.mapper.username

        validated_tasks.sort(key=mapper_username)

        user_dict = {}
        for user in project_users:
            user_dict[user] = {}

        tasks_as_tasks_dict = {}
        task_dict = {}
        issue_dict = {}
        i = 0
        current_username = None
        for task in validated_tasks:
            tasks_as_tasks_dict[task.id] = task
            if (i == 0):
                current_username = task.mapper.username

            if (task.mapper.username != current_username):
                user_dict[current_username] = deepcopy(task_dict)
                current_username = task.mapper.username
                task_dict.clear()

            issue_dict.clear()

            for hist in task.task_history:
                if (len(hist.task_mapping_issues) > 0):
                    for issue in hist.task_mapping_issues:
                        issue_dict[issue.issue] = issue.count

            if (len(issue_dict.keys()) > 0):
                task_dict[task.id] = deepcopy(issue_dict)
            #*** Uncomment this else statement if rows with all zeros should be shown in detailed view ***
            #*** Comment to hide zero rows in detailed view ***
            else:
                task_dict[task.id] = {}

            i += 1

        user_dict[current_username] = task_dict

        return user_dict, project_users, len(validated_tasks), tasks_as_tasks_dict

    @staticmethod
    def build_issue_totals_table(user_dict, project_users):
        """ Get category names and create table of issue totals: mapped users -> arrayOfMappingIssueTotals """
        """ Mapping issue totals are sorted by mapping issue category_id """
        """ A row of totals is included at the bottom """
        categories_dto = MappingIssueCategoryService.get_all_mapping_issue_categories(True)
        categories = categories_dto.categories

        category_index_dict = {}
        category_names_dict = {}
        max_category_index = 0
        for category in categories:
            category_index_dict[category.name] = category.category_id
            category_names_dict[category.category_id] = category.name
            if (category.category_id > max_category_index):
                max_category_index = category.category_id

        data_table = {}
        totals = np.zeros(max_category_index + 1, dtype='i')
        for user in project_users:
            data_table[user] = np.zeros(max_category_index + 1, dtype='i')
            for task in user_dict[user]:
                for issue in user_dict[user][task]:  #issue is the name of the issue
                    category_index = category_index_dict[issue]
                    issue_count = user_dict[user][task][issue]
                    data_table[user][category_index] += issue_count
                    totals[category_index] += issue_count

        return data_table, category_index_dict, category_names_dict, max_category_index, totals

