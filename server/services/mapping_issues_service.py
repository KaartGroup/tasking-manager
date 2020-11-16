from server.models.postgis.mapping_issues import MappingIssueCategory
from server.models.postgis.task import TaskMappingIssue, TaskHistory, Task
from server.models.postgis.project import Project
from server.models.dtos.mapping_issues_dto import MappingIssueCategoryDTO
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


class MappingIssueService:

    @staticmethod
    def get_mapping_issues(projectId: int):  #projectId: int, detailedView: boolean
        """
        Returns a csv string of all mapping issues associated with the given project summed and sorted by user
        raises: NotFound
        """

        detailedView = False  #TODO remove once detailedView is added as an argument

        allProjectTasks = Task.get_all_tasks(projectId)
        validatedTasks = []
        projectUsers = []
        for task in allProjectTasks:
            if (task.validated_by == None):
                continue
            else:
                validatedTasks.append(task)
                if (task.mapper.username in projectUsers):
                    continue
                else:
                    projectUsers.append(task.mapper.username)

        userDict = {}
        for user in projectUsers:
            userDict[user] = {}

        taskDict = {}
        issueDict = {}
        i = 0
        currentUsername = None
        for task in validatedTasks:
            if (i == 0):
                currentUsername = task.mapper.username

            if (task.mapper.username != currentUsername):
                userDict[currentUsername] = deepcopy(taskDict)
                currentUsername = task.mapper.username
                taskDict.clear()

            #print(task.id, task.mapper.username)
            issueDict.clear()

            for hist in task.task_history:
                if (len(hist.task_mapping_issues) > 0):
                    for issue in hist.task_mapping_issues:
                        issueDict[issue.issue] = issue.count

            if (len(issueDict.keys()) > 0):
                taskDict[task.id] = deepcopy(issueDict)

            i += 1

        userDict[currentUsername] = taskDict

        #print("end: ", userDict)


        #User, taskID:validated by, issues......
        #    ,  3 : validator     ,  #   ,  #   ,  #  ...
        #    ,  6 : validator     ,  #   ,  #   ,  #  ...
        #totals,                    ,  #   ,  #   ,  #  ...

        #grand totals at the bottom


        categories_dto = MappingIssueCategoryService.get_all_mapping_issue_categories(True)
        categories = categories_dto.categories

        categoryIndexDict = {}
        categoryNamesDict = {}
        maxCategoryIndex = 0
        for category in categories:
            #print(category.category_id, category.name, category.description, category.archived)
            categoryIndexDict[category.name] = category.category_id
            categoryNamesDict[category.category_id] = category.name
            if (category.category_id > maxCategoryIndex):
                maxCategoryIndex = category.category_id

        numCategories = len(categoryIndexDict.keys())
        numValidatedTasks = len(validatedTasks)
        numUsers = len(projectUsers)

        #print(categoryIndexDict)
        #print(categoryNamesDict)


        csvString = None
        if (detailedView):
            #print("Detailed view not yet implemented")
            return "TODO implement detailed view"
        else:
            dataTable = {}
            totals = np.zeros(maxCategoryIndex + 1, dtype='i')
            for user in projectUsers:
                dataTable[user] = np.zeros(maxCategoryIndex + 1, dtype='i')
                for task in userDict[user]:
                    for issue in userDict[user][task]:  #issue is the name of the issue
                        #print(task, issue, userDict[user][task][issue])
                        categoryIndex = categoryIndexDict[issue]
                        issueCount = userDict[user][task][issue]
                        dataTable[user][categoryIndex] += issueCount
                        totals[categoryIndex] += issueCount

            #print(dataTable)

            allRows = []
            issueNamesRow = ['Issue']
            possibleIndices = categoryNamesDict.keys()
            for i in range(1, maxCategoryIndex + 1):  #category id is the category's index. Category ids start at 1
                if (i in possibleIndices):
                    issueNamesRow.append(categoryNamesDict[i])
                else:
                    issueNamesRow.append("")

            allRows.append(",".join(issueNamesRow))

            for user in projectUsers:
                row = []
                row.append(user)
                #print(dataTable[user])
                for issueCount in dataTable[user]:
                        row.append(str(issueCount))
                row.pop(1)

                allRows.append(",".join(row))

            totalsRow = ['Total']
            for value in totals:
                totalsRow.append(str(value))
            totalsRow.pop(1)

            allRows.append(",".join(totalsRow))

            csvString = "\n".join(allRows)
            #print(csvString)

        return csvString

