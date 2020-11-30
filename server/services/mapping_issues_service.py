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

    def get_mapping_issues(self, projectId: int, detailedView: str):
        """
        Returns a csv string of all mapping issues associated with the given project summed and sorted by user
        raises: NotFound
        """
        detailed = False
        if (detailedView == "true"):
            detailed = True

        #userDict {str username : {int task (taskId) : {str issue : str issueCount}}}
        #projectUsers is a list of users on the project with no duplicates
        #int numValidatedTasks
        #tasksAsTasksDict {int taskId : task}
        userDict, projectUsers, numValidatedTasks, tasksAsTasksDict = MappingIssueExporter.compile_validated_tasks_by_user(projectId)

        #dataTable {str user : numpy array of user issue totals}
        #categoryIndexDict {str issue : int issueId}
        #categoryNamesDict {int issueId : str issue}
        #maxCategoryIndex: int, max issueId
        #totals: numpy array of project issue totals
        dataTable, categoryIndexDict, categoryNamesDict, maxCategoryIndex, totals = MappingIssueExporter.build_issue_totals_table(userDict, projectUsers)

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
        projectContribDTO = StatsService.get_user_contributions(projectId)

        allRows = []
        issueNamesRow = []
        if (detailed):
           issueNamesRow.append('Username (tasks mapped)')
           issueNamesRow.append('taskId: ValidatedBy')
        else:
            issueNamesRow.append('Username (tasks mapped)')

        possibleIndices = categoryNamesDict.keys()
        for i in range(1, maxCategoryIndex + 1):  #category id is the category's index. Category ids start at 1
            if (i in possibleIndices):
                issueNamesRow.append(categoryNamesDict[i])
            else:
                issueNamesRow.append('')

        allRows.append(','.join(issueNamesRow))

        for user in projectUsers:
            row = []

            if (detailed):
                row.append('')
                i = 0
                for task in userDict[user]:
                    validator = User.get_by_id(self, tasksAsTasksDict[task].validated_by).username

                    singleTaskRow = []
                    if (i == 0):
                        singleTaskRow.append(user)
                    else:
                        singleTaskRow.append('')
                    singleTaskRow.append(str(task) + ': ' + validator)
                    singleTaskRowIssueCounts = np.zeros(maxCategoryIndex + 1, dtype='i')
                    for issue in userDict[user][task]:
                        categoryIndex = categoryIndexDict[issue]
                        singleTaskRowIssueCounts[categoryIndex] = userDict[user][task][issue]

                    for issueCount in singleTaskRowIssueCounts:
                        singleTaskRow.append(str(issueCount))
                    singleTaskRow.pop(2)
                    allRows.append(",".join(singleTaskRow))

                    i += 1

            numMappedTasks = -1
            for userContrib in projectContribDTO.user_contributions:
                if (userContrib.username == user):
                    numMappedTasks = userContrib.mapped
                    break

            row.append(user + ' (' + str(numMappedTasks) + ')')

            for issueCount in dataTable[user]:
                row.append(str(issueCount))
            row.pop(1)

            if (detailed):
                row[1] = ''
                row[0] = user + ' totals (' + str(numMappedTasks) + ')'

            allRows.append(','.join(row))
            if (detailed):
                allRows[-1] = allRows[-1] + '\n'

        totalsRow = ['Project Totals']
        for value in totals:
            totalsRow.append(str(value))
        if (not detailed):
            totalsRow.pop(1)
        else:
            totalsRow[1] = ''

        allRows.append(','.join(totalsRow))

        csvString = '\n'.join(allRows)
        #print(csvString)

        return csvString


    @staticmethod
    def compile_validated_tasks_by_user(projectId: int):
        allProjectTasks = Task.get_all_tasks(projectId)
        validatedTasks = []
        projectUsers = []
        for task in allProjectTasks:
            if (task.task_status == TaskStatus.VALIDATED.value):
                validatedTasks.append(task)
                if (task.mapper.username in projectUsers):
                    continue
                else:
                    projectUsers.append(task.mapper.username)
            else:
                continue

        def mapper_username(task):
            return task.mapper.username

        validatedTasks.sort(key=mapper_username)

        userDict = {}
        for user in projectUsers:
            userDict[user] = {}

        tasksAsTasksDict = {}
        taskDict = {}
        issueDict = {}
        i = 0
        currentUsername = None
        for task in validatedTasks:
            tasksAsTasksDict[task.id] = task
            if (i == 0):
                currentUsername = task.mapper.username

            if (task.mapper.username != currentUsername):
                userDict[currentUsername] = deepcopy(taskDict)
                currentUsername = task.mapper.username
                taskDict.clear()

            issueDict.clear()

            for hist in task.task_history:
                if (len(hist.task_mapping_issues) > 0):
                    for issue in hist.task_mapping_issues:
                        issueDict[issue.issue] = issue.count

            if (len(issueDict.keys()) > 0):
                taskDict[task.id] = deepcopy(issueDict)
            #*** Uncomment this else statement if rows with all zeros should be shown in detailed view ***
            #*** Comment to hide zero rows in detailed view ***
            else:
                taskDict[task.id] = {}

            i += 1

        userDict[currentUsername] = taskDict

        return userDict, projectUsers, len(validatedTasks), tasksAsTasksDict

    @staticmethod
    def build_issue_totals_table(userDict, projectUsers):
        """ Get category names and create table of issue totals: mapped users -> arrayOfMappingIssueTotals """
        """ Mapping issue totals are sorted by mapping issue category_id """
        """ A row of totals is included at the bottom """
        categories_dto = MappingIssueCategoryService.get_all_mapping_issue_categories(True)
        categories = categories_dto.categories

        categoryIndexDict = {}
        categoryNamesDict = {}
        maxCategoryIndex = 0
        for category in categories:
            categoryIndexDict[category.name] = category.category_id
            categoryNamesDict[category.category_id] = category.name
            if (category.category_id > maxCategoryIndex):
                maxCategoryIndex = category.category_id

        numCategories = len(categoryIndexDict.keys())
        numUsers = len(projectUsers)

        dataTable = {}
        totals = np.zeros(maxCategoryIndex + 1, dtype='i')
        for user in projectUsers:
            dataTable[user] = np.zeros(maxCategoryIndex + 1, dtype='i')
            for task in userDict[user]:
                for issue in userDict[user][task]:  #issue is the name of the issue
                    categoryIndex = categoryIndexDict[issue]
                    issueCount = userDict[user][task][issue]
                    dataTable[user][categoryIndex] += issueCount
                    totals[categoryIndex] += issueCount

        return dataTable, categoryIndexDict, categoryNamesDict, maxCategoryIndex, totals

