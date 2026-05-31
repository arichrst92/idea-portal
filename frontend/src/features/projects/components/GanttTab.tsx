/**
 * GanttTab — TSK-065 Timeline visualization for Phase + Task.
 *
 * Pakai gantt-task-react. Map:
 *  - Project        → root task (project span)
 *  - Phase          → task (target_date, progress_pct)
 *  - Epic           → task (grouped under phase)
 *  - Task           → task (due_date, priority color)
 *
 * View mode switcher: Day / Week / Month.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Empty, Radio, Space, Spin, Typography } from 'antd';
import dayjs from 'dayjs';
import { Gantt, Task, ViewMode } from 'gantt-task-react';
import 'gantt-task-react/dist/index.css';

import {
  getProject,
  listPhases,
  listProjectEpics,
  listTasks,
  priorityColor,
} from '@/api/projects';

const { Text } = Typography;

interface GanttTabProps {
  projectId: string;
}

export function GanttTab({ projectId }: GanttTabProps) {
  const [view, setView] = useState<ViewMode>(ViewMode.Week);

  const projectQ = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });
  const phasesQ = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => listPhases(projectId),
  });
  const epicsQ = useQuery({
    queryKey: ['epics', projectId],
    queryFn: () => listProjectEpics(projectId),
  });
  const tasksQ = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => listTasks(projectId),
  });

  const ganttTasks: Task[] = useMemo(() => {
    if (!projectQ.data || !phasesQ.data) return [];
    const out: Task[] = [];
    const project = projectQ.data;
    const phases = phasesQ.data;
    const epics = epicsQ.data ?? [];
    const tasks = tasksQ.data ?? [];

    // Project span — bounded by start_date/end_date
    const projectStart = project.start_date
      ? dayjs(project.start_date).toDate()
      : dayjs().startOf('month').toDate();
    const projectEnd = project.end_date
      ? dayjs(project.end_date).toDate()
      : dayjs().add(3, 'month').toDate();

    out.push({
      id: `project-${project.id}`,
      type: 'project',
      name: `📦 ${project.code} — ${project.name}`,
      start: projectStart,
      end: projectEnd,
      progress: Math.round(Number(project.overall_progress_pct ?? 0)),
      hideChildren: false,
      styles: {
        backgroundColor: '#0071E3',
        backgroundSelectedColor: '#005ec0',
        progressColor: '#34C759',
        progressSelectedColor: '#22a049',
      },
    });

    // Phases
    phases.forEach((p, idx) => {
      // Phase start = prev phase end or project start
      const prevEnd = idx > 0
        ? (phases[idx - 1].target_date
            ? dayjs(phases[idx - 1].target_date!).toDate()
            : projectStart)
        : projectStart;
      const phaseEnd = p.target_date
        ? dayjs(p.target_date).toDate()
        : dayjs(prevEnd).add(2, 'week').toDate();

      out.push({
        id: `phase-${p.id}`,
        type: 'task',
        name: `🎯 ${p.name}`,
        start: prevEnd,
        end: phaseEnd,
        progress: Math.round(Number(p.progress_pct)),
        project: `project-${project.id}`,
        styles: {
          backgroundColor: p.is_overdue ? '#FF3B30' : '#AF52DE',
          backgroundSelectedColor: p.is_overdue ? '#cf2920' : '#8a3eaf',
          progressColor: '#34C759',
          progressSelectedColor: '#22a049',
        },
      });

      // Epics under this phase
      const phaseEpics = epics.filter((e) => e.phase_id === p.id);
      phaseEpics.forEach((e) => {
        const epicTasks = tasks.filter((t) => t.epic_id === e.id);
        const epicProgress = e.task_count > 0
          ? Math.round((e.completed_task_count / e.task_count) * 100)
          : 0;
        // Epic span = min(tasks.due_date) to max(tasks.due_date) or phase span
        const taskDates = epicTasks
          .map((t) => t.due_date)
          .filter((d): d is string => d !== null)
          .map((d) => dayjs(d).toDate());
        const epicStart = taskDates.length > 0
          ? new Date(Math.min(...taskDates.map((d) => d.getTime())))
          : prevEnd;
        const epicEnd = taskDates.length > 0
          ? new Date(Math.max(...taskDates.map((d) => d.getTime())))
          : phaseEnd;

        out.push({
          id: `epic-${e.id}`,
          type: 'task',
          name: `   📌 ${e.name}`,
          start: epicStart,
          end: epicEnd,
          progress: epicProgress,
          project: `project-${project.id}`,
          styles: {
            backgroundColor: e.color ?? '#32ADE6',
            backgroundSelectedColor: '#0b8bc2',
            progressColor: '#34C759',
            progressSelectedColor: '#22a049',
          },
        });

        // Tasks under this epic (only those with due_date)
        epicTasks
          .filter((t) => t.due_date)
          .forEach((t) => {
            const tEnd = dayjs(t.due_date!).toDate();
            const tStart = dayjs(t.due_date!).subtract(3, 'day').toDate();
            const tProgress = t.status === 'DONE' ? 100 :
              t.status === 'IN_REVIEW' ? 80 :
                t.status === 'IN_PROGRESS' ? 50 :
                  t.status === 'TODO' ? 10 : 0;
            const pColor = priorityColor(t.priority);
            // Strip CSS var() to extract fallback hex
            const colorMatch = pColor.match(/#[0-9a-fA-F]{6}/);
            const bg = colorMatch ? colorMatch[0] : '#0071E3';

            out.push({
              id: `task-${t.id}`,
              type: 'task',
              name: `      [${t.slug}] ${t.title}`,
              start: tStart,
              end: tEnd,
              progress: tProgress,
              project: `project-${project.id}`,
              styles: {
                backgroundColor: bg,
                backgroundSelectedColor: bg,
                progressColor: '#34C759',
                progressSelectedColor: '#22a049',
              },
            });
          });
      });
    });

    return out;
  }, [projectQ.data, phasesQ.data, epicsQ.data, tasksQ.data]);

  if (projectQ.isLoading || phasesQ.isLoading) {
    return <Spin tip="Memuat timeline..." style={{ marginTop: 40 }}><div style={{ minHeight: 24 }} /></Spin>;
  }

  if (ganttTasks.length === 0) {
    return (
      <Empty description="Belum ada Phase / Task untuk di-render. Tambah dari tab Hierarchy." />
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Timeline view: Project › Phase › Epic › Task. Phase berdasarkan target_date,
          Task berdasarkan due_date. Progress dari kombinasi status + subtask completion.
        </Text>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>View:</Text>
          <Radio.Group value={view} onChange={(e) => setView(e.target.value)} size="small">
            <Radio.Button value={ViewMode.Day}>Day</Radio.Button>
            <Radio.Button value={ViewMode.Week}>Week</Radio.Button>
            <Radio.Button value={ViewMode.Month}>Month</Radio.Button>
            <Radio.Button value={ViewMode.Year}>Year</Radio.Button>
          </Radio.Group>
        </Space>
      </div>

      <div
        style={{
          background: '#fff',
          border: '1px solid rgba(0,0,0,0.06)',
          borderRadius: 12,
          padding: 8,
          overflow: 'auto',
        }}
      >
        <Gantt
          tasks={ganttTasks}
          viewMode={view}
          listCellWidth="240px"
          columnWidth={view === ViewMode.Day ? 60 : view === ViewMode.Week ? 80 : view === ViewMode.Month ? 110 : 250}
          rowHeight={36}
          headerHeight={44}
          fontFamily="-apple-system, BlinkMacSystemFont, 'Inter', sans-serif"
          fontSize="12"
          barCornerRadius={4}
          barFill={70}
          locale="id"
        />
      </div>

      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 8 }}>
        Tip: scroll horizontal untuk lihat seluruh timeline. Hover bar untuk lihat detail tanggal.
        Task tanpa due_date tidak ditampilkan di Gantt — set due_date dulu dari TaskDrawer.
      </Text>
    </div>
  );
}
