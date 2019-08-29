"""empty message

Revision ID: 0a6b82b55983
Revises: 3ee58dee57c9
Create Date: 2018-09-04 19:09:45.866336

"""
from alembic import op
import sqlalchemy as sa
import re
from server.models.postgis.message import MessageType
from server.models.postgis.project import Project


# revision identifiers, used by Alembic.
revision = '0a6b82b55983'
down_revision = '3ee58dee57c9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('messages', sa.Column('message_type', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('project_id', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('task_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_message_projects', 'messages', 'projects', ['project_id'], ['id'])
    op.create_index(op.f('ix_messages_message_type'), 'messages', ['message_type'], unique=False)
    op.create_index(op.f('ix_messages_project_id'), 'messages', ['project_id'], unique=False)
    op.create_index(op.f('ix_messages_task_id'), 'messages', ['task_id'], unique=False)
    # ### end Alembic commands ###

    project_task_re = re.compile('project/(\d+)/\?task=(\d+)')
    validated_notification_re = re.compile('been validated')
    invalidated_notification_re = re.compile('been marked invalid')
    mention_notification_re = re.compile('You were mentioned')
    welcome_re = re.compile('Welcome to the HOT Tasking Manager')
    message_all_re = re.compile('project/(\d+)\?tab=chat')

    project_existence = {}

    # Attempt to classify existing messages
    messages = conn.execute('select * from messages')
    for message in messages:
        message_type = None
        project_id = None
        task_id = None

        match = project_task_re.search(message.subject)
        if match:
            project_id = match.group(1)
            task_id = match.group(2)

        if validated_notification_re.search(message.subject):
            message_type = MessageType.VALIDATION_NOTIFICATION.value
        elif invalidated_notification_re.search(message.subject):
            message_type = MessageType.INVALIDATION_NOTIFICATION.value
        elif mention_notification_re.search(message.subject):
            message_type = MessageType.MENTION_NOTIFICATION.value
        elif welcome_re.search(message.subject):
            message_type = MessageType.SYSTEM.value

        # Look for direct messages from project managers
        if message_type is None and project_id is None:
            match = message_all_re.search(message.message)
            if match:
                project_id = match.group(1)
                message_type = MessageType.BROADCAST.value

        # Update message with assigned classification
        if message_type is not None or project_id is not None:
            if task_id is None:
                task_id = 'null'
            if project_id is None:
                project_id = 'null'
            if message_type is None:
                message_type = 'null'
            # If we haven't checked yet if this project exists, check now and cache result
            if project_id not in project_existence:
                project = conn.execute('select * from projects where id = ' + str(project_id)).first()
                project_existence[project_id] = (project is not None)

            # Only process messages from projects that still exist
            if project_existence[project_id]:
                query = 'update messages ' + \
                        'set message_type=' + str(message_type) + \
                            ', project_id=' + str(project_id) + \
                            ', task_id=' + str(task_id) + \
                        ' where id = ' + str(message.id)

                op.execute(query)

def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_messages_task_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_project_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_message_type'), table_name='messages')
    op.drop_constraint('fk_message_projects', 'messages', type_='foreignkey')
    op.drop_column('messages', 'task_id')
    op.drop_column('messages', 'project_id')
    op.drop_column('messages', 'message_type')
    # ### end Alembic commands ###