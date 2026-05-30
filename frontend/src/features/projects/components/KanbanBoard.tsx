/**
 * KanbanBoard — drag-drop kanban (TSK-064 polish).
 *
 * Wraps tasks dalam DragDropContext + 6 Droppable columns + Draggable cards.
 * onDragEnd → callback parent untuk update task status.
 * Column accent color per status. Sticky header with count.
 */

import { DragDropContext, Draggable, Droppable, type DropResult } from '@hello-pangea/dnd';
import { Typography } from 'antd';

import {
  TASK_STATUSES,
  taskStatusColor,
  type Task,
  type TaskStatus,
} from '@/api/projects';

import { KanbanCard } from './KanbanCard';

const { Text } = Typography;

const COLUMN_ACCENT: Record<TaskStatus, string> = {
  BACKLOG: 'rgba(110, 110, 115, 0.08)',
  TODO: 'rgba(0, 113, 227, 0.06)',
  IN_PROGRESS: 'rgba(255, 149, 0, 0.07)',
  IN_REVIEW: 'rgba(175, 82, 222, 0.06)',
  DONE: 'rgba(52, 199, 89, 0.07)',
  BLOCKED: 'rgba(255, 59, 48, 0.07)',
};

const COLUMN_LABEL: Record<TaskStatus, string> = {
  BACKLOG: 'Backlog',
  TODO: 'To Do',
  IN_PROGRESS: 'In Progress',
  IN_REVIEW: 'In Review',
  DONE: 'Done',
  BLOCKED: 'Blocked',
};

interface KanbanBoardProps {
  tasks: Task[];
  onCardClick: (task: Task) => void;
  /** Called when a task is dropped to a different column. */
  onStatusChange: (taskId: string, newStatus: TaskStatus) => void;
}

export function KanbanBoard({ tasks, onCardClick, onStatusChange }: KanbanBoardProps) {
  const grouped: Record<TaskStatus, Task[]> = {
    BACKLOG: [], TODO: [], IN_PROGRESS: [], IN_REVIEW: [], DONE: [], BLOCKED: [],
  };
  tasks.forEach((t) => grouped[t.status].push(t));

  const handleDragEnd = (result: DropResult) => {
    if (!result.destination) return;
    const newStatus = result.destination.droppableId as TaskStatus;
    const oldStatus = result.source.droppableId as TaskStatus;
    if (newStatus === oldStatus && result.source.index === result.destination.index) return;
    if (newStatus !== oldStatus) {
      onStatusChange(result.draggableId, newStatus);
    }
  };

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, minmax(240px, 1fr))',
          gap: 12,
          overflowX: 'auto',
          paddingBottom: 8,
        }}
      >
        {TASK_STATUSES.map((status) => {
          const accentColor = taskStatusColor(status);
          const colTasks = grouped[status];
          return (
            <Droppable droppableId={status} key={status}>
              {(provided, snapshot) => (
                <div
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  style={{
                    background: snapshot.isDraggingOver
                      ? 'rgba(0, 113, 227, 0.08)'
                      : COLUMN_ACCENT[status],
                    border: `1px solid ${snapshot.isDraggingOver ? 'var(--ide-blue, #0071E3)' : 'transparent'}`,
                    borderRadius: 12,
                    padding: 10,
                    minHeight: 280,
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'all 0.15s',
                  }}
                >
                  {/* Sticky column header */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      paddingBottom: 8,
                      marginBottom: 6,
                      borderBottom: `2px solid ${accentColor}`,
                      position: 'sticky',
                      top: 0,
                      zIndex: 1,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          width: 8, height: 8, borderRadius: '50%',
                          background: accentColor,
                        }}
                      />
                      <Text strong style={{ fontSize: 12, color: accentColor }}>
                        {COLUMN_LABEL[status]}
                      </Text>
                    </div>
                    <Text
                      type="secondary"
                      style={{
                        fontSize: 11,
                        background: 'rgba(0,0,0,0.05)',
                        padding: '2px 8px',
                        borderRadius: 10,
                      }}
                    >
                      {colTasks.length}
                    </Text>
                  </div>

                  {/* Draggable cards */}
                  <div style={{ flex: 1, minHeight: 100 }}>
                    {colTasks.map((task, index) => (
                      <Draggable draggableId={task.id} index={index} key={task.id}>
                        {(dragProvided, dragSnapshot) => (
                          <div
                            ref={dragProvided.innerRef}
                            {...dragProvided.draggableProps}
                            {...dragProvided.dragHandleProps}
                            style={{
                              ...dragProvided.draggableProps.style,
                              opacity: dragSnapshot.isDragging ? 0.9 : 1,
                              transform: dragSnapshot.isDragging
                                ? `${dragProvided.draggableProps.style?.transform ?? ''} rotate(1.5deg)`
                                : dragProvided.draggableProps.style?.transform,
                            }}
                          >
                            <KanbanCard task={task} onClick={() => onCardClick(task)} />
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                    {colTasks.length === 0 && !snapshot.isDraggingOver && (
                      <div
                        style={{
                          padding: '24px 8px',
                          textAlign: 'center',
                          color: 'var(--ide-ink3, #6e6e73)',
                          fontSize: 11,
                          fontStyle: 'italic',
                        }}
                      >
                        Drop tasks di sini
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Droppable>
          );
        })}
      </div>
    </DragDropContext>
  );
}
