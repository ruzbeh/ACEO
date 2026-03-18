import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { InitiativesPage } from './pages/InitiativesPage';
import { InitiativeDetailPage } from './pages/InitiativeDetailPage';
import { TasksPage } from './pages/TasksPage';
import { TaskDetailPage } from './pages/TaskDetailPage';
import { BudgetPage } from './pages/BudgetPage';
import { AgentsPage } from './pages/AgentsPage';

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/initiatives" replace />} />
        <Route path="initiatives" element={<InitiativesPage />} />
        <Route path="initiatives/:id" element={<InitiativeDetailPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="tasks/:id" element={<TaskDetailPage />} />
        <Route path="budget" element={<BudgetPage />} />
        <Route path="agents" element={<AgentsPage />} />
      </Route>
    </Routes>
  );
}
