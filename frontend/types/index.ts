export interface User {
  id: string
  email: string
  username: string
  created_at: string
}

export interface Todo {
  id: string
  user_id: string
  title: string
  description: string | null
  priority: 'low' | 'medium' | 'high'
  due_date: string | null
  reminder_at: string | null
  status: 'pending' | 'in-progress' | 'done'
  created_at: string
  updated_at: string | null
}

export interface TodoStats {
  total: number
  completed: number
  pending: number
  overdue: number
}

export type TodoCreate = Pick<Todo, 'title'> &
  Partial<Pick<Todo, 'description' | 'priority' | 'due_date' | 'reminder_at' | 'status'>>

export type TodoUpdate = Partial<
  Pick<Todo, 'title' | 'description' | 'priority' | 'due_date' | 'reminder_at' | 'status'>
>

export type NotificationType = 'reminder_due' | 'overdue'

export interface Notification {
  id: string
  user_id: string
  todo_id: string
  todo_title: string
  notification_type: NotificationType
  triggered_at: string
  delivered_at: string
  read: boolean
}
