export interface HealthResponse { status: string; version?: string; uptime?: number }
export interface ChatResponse { text: string; entity_state?: EntityState; task_session?: string }
export interface EntityState { mood: string; energy: number; goals: EntityGoal[]; last_scan?: string; thoughts?: string[] }
export interface EntityGoal { id: string; goal: string; progress: number; priority: number; deadline?: string; completed: boolean }
export interface EntityProcessResponse { text: string; entity_state: EntityState; action?: string }
export interface Strategy { title: string; description: string; steps: string[]; expected_outcome: string }
export interface DocumentUploadResponse { success: boolean; doc_id?: string; message: string }
export interface DocumentsResponse { has_docs: boolean; count?: number; documents?: string[] }
export interface Reminder { id: string; title: string; description: string; due_date: string; completed: boolean; created_at: string }
export interface RemindersResponse { reminders: Reminder[] }
export interface LiveKitTokenResponse { token: string; url: string; room: string }
export interface WorkflowResponse { execution_id: string; status: string; current_step: string; response: string }
export interface SystemStats { cpu_percent: number; memory_percent: number; memory_gb: number; total_memory_gb: number; disk_percent: number; disk_gb: number; total_disk_gb: number; network_rx: number; network_tx: number; platform: string; hostname: string; uptime: number }
export interface SystemProcess { pid: number; name: string; cpu_percent: number; memory_mb: number }
export interface SystemInfo { platform: string; hostname: string; kernel: string; cpu: string; cores: number; memory_gb: number }
export interface Action { id: string; name: string; description: string; category: string }
export interface WebSearchResult { title: string; url: string; snippet: string }
export interface WeatherResponse { city: string; temperature: number; condition: string; humidity: number; wind_speed: number }
export interface EmailConfig { smtp_server: string; smtp_port: number; imap_server: string; email: string; configured: boolean }
export interface Email { id: string; from: string; to: string; subject: string; body: string; date: string; read: boolean }
export interface CalendarEvent { id: string; title: string; date: string; time: string; duration_min: number; description: string }
export interface Contact { id: string; name: string; email: string; phone: string; company: string; notes: string }
export interface BusinessSummary { total_emails: number; unread_emails: number; upcoming_events: number; total_contacts: number }
export interface ResearchResult { topic: string; summary: string; sources: { title: string; url: string; relevance: number }[] }
export interface LifeDashboard { date: string; tasks_today: number; tasks_completed: number; calories_burned: number; water_ml: number; sleep_hours: number; mood: string; habits_streak: number; finance?: { balance: number; income: number; expenses: number; transaction_count: number }; health?: { workouts_today: number; water_today_ml: number; sleep_last?: { hours: number; quality: number }; last_weight_kg?: number; calories_today: number; streak_days: number } }
export interface LifeFinance { balance: number; monthly_spending: number; monthly_income: number; income: number; expenses: number; transaction_count: number; recent_transactions: LifeTransaction[] }
export interface LifeTransaction { id: string; amount: number; category: string; description: string; type: "income" | "expense"; date: string }
export interface LifeBudget { category: string; limit: number; spent: number; remaining: number; budget: number; pct_used: number; status: "under" | "warning" | "over" }
export interface LifeSubscription { id: string; name: string; cost: number; billing_cycle: string; next_billing: string }
export interface LifeHealthSummary { workouts_this_week: number; workouts_today: number; total_calories_burned: number; calories_today: number; calories_consumed: number; water_ml: number; water_today_ml: number; sleep_hours: number; sleep_quality: number; sleep_last?: { hours: number; quality: number }; weight_kg?: number; last_weight_kg?: number; streak_days: number }
export interface LifeTask { id: string; title: string; priority: number; due_date: string; estimated_min: number; completed: boolean }
export interface LifeHabit { id: string; name: string; streak: number; longest_streak: number; last_logged: string; done_today: boolean; logs: { date: string; value: number }[] }
export interface LifeGoal { id: string; title: string; goal: string; target_date: string; progress: number; milestones: { description: string; achieved: boolean }[] }
export interface LifeJournalEntry { id: string; content: string; tags: string[]; created_at: string; time?: string; date?: string }
export interface MoodEntry { date: string; mood: number; note: string }
export interface TradingPortfolio { cash: number; total_value: number; holdings: TradingHolding[] }
export interface TradingHolding { symbol: string; name: string; shares: number; avg_price: number; current_price: number; total_value: number; gain_loss_percent: number }
export interface TradeHistoryEntry { id: string; symbol: string; type: "buy" | "sell"; shares: number; price: number; total: number; date: string }
export interface StockAnalysis { symbol: string; current_price: number; change_percent: number; high_52w: number; low_52w: number; volume: number; avg_volume: number; pe_ratio?: number; market_cap?: number; recommendation: string }
export interface TradingStrategy { id: string; name: string; description: string; type: string; performance: { return_percent: number; trades: number; win_rate: number } }
export interface MarketplacePlugin { id: string; name: string; description: string; version: string; author: string; price: number; category: string; downloads: number; rating: number; installed: boolean }
export interface SmartHomeDevice { id: string; name: string; type: string; ip: string; status: string; room: string; brightness?: number; temperature?: number }
export interface SmartHomeScene { id: string; name: string; devices: { device_id: string; state: Record<string, unknown> }[] }
export interface DeviceHubStats { total: number; online: number; offline: number; types: Record<string, number> }
export interface MoneyBalance { balance: number; total_grants: number; total_spent: number }
export interface MoneyTransaction { id: string; amount: number; purpose: string; timestamp: string; type: "grant" | "spend" }
export interface JarvisStatus { online: boolean; mode: string; uptime: number; active_agents: number; memory_usage: number }
export interface JarvisHUD { status: string; current_task: string; recent_thoughts: string[]; system_health: string }
export interface ScanResult { type: string; scan_id: string; devices_found: number; devices: { ip: string; mac: string; hostname: string; open_ports: number[] }[]; duration_sec: number }
export interface PropagationStatus { active: boolean; campaign_id?: string; infected: number; targets: number; logs: PropagationLog[] }
export interface PropagationLog { timestamp: string; level: string; message: string }
export interface HealingStatus { healthy: boolean; last_check: string; services: { name: string; status: string; last_restart: string }[] }
export interface HealingSummary { total_incidents: number; resolved: number; uptime_percent: number; recent_actions: { time: string; action: string; result: string }[] }
export interface EnterpriseAuthResponse { token: string; user: { id: string; email: string; name: string; tier: string } }
export interface DeployResponse { success: boolean; platform: string; url?: string; logs: string[] }
export interface CodeResponse { code: string; language: string; explanation: string }
export interface SwarmResponse { swarm_id: string; status: string; agents: { id: string; role: string; status: string }[]; result?: string }
export interface BotEvent { type: string; label: string; timestamp: number }
export interface BotTranscript { type: "transcript"; role: "user" | "assistant"; text: string }
export interface BotStatus { type: "status"; state: "listening" | "speaking" | "idle" | "thinking" }
export interface GroqMessage { role: "system" | "user" | "assistant"; content: string }
