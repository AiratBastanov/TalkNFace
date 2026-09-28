import { z } from 'zod';
import { CatalogReferenceSchema, PublishedCatalogScenarioSchema } from './catalog.ts';

// App-only inputs/DTOs. No private definition or solver data is imported here.
export const SettingsSchema = z.strictObject({
  sphere: z.enum(['supply', 'team']),
  topic: z.enum(['launch', 'planned', 'urgent', 'reprioritize']).nullable(),
  difficulty: z.enum(['beginner', 'normal', 'advanced']),
  tone: z.enum(['friendly', 'neutral', 'skeptical']),
  opponentRole: z.enum(['director', 'account_manager', 'specialist', 'team_lead']).nullable(),
  opponentGoals: z.enum(['cashflow', 'margin', 'protect_load', 'deliver_scope']).nullable(),
});
export type Settings = z.infer<typeof SettingsSchema>;
export type SettingField = keyof Settings;
export const DEFAULT_SETTINGS: Settings = {
  sphere: 'supply', topic: 'launch', difficulty: 'normal', tone: 'neutral',
  opponentRole: 'director', opponentGoals: 'cashflow',
};
export const CONTROLS: { field: SettingField; label: string; help: string; options: { id: string; label: string; description: string; sphere?: Settings["sphere"]; }[] }[] = [
  {
    "field": "sphere",
    "label": "Сфера",
    "help": "Меняет предмет переговоров, интересы и единицы измерения.",
    "options": [
      {
        "id": "supply",
        "label": "Промышленные закупки",
        "description": "Цена в тысячах, график поставки, предоплата в процентах."
      },
      {
        "id": "team",
        "label": "Управление командой",
        "description": "Объём в часах, срок в днях, помощник и перенос отчёта."
      }
    ]
  },
  {
    "field": "topic",
    "label": "Тема",
    "help": "Меняет обязательные условия и доступные ресурсы. Цель игрока проверяется заново.",
    "options": [
      {
        "id": "launch",
        "label": "Запуск производства",
        "description": "Не менее 40% партии к дню 7.",
        "sphere": "supply"
      },
      {
        "id": "planned",
        "label": "Плановая поставка",
        "description": "Можно получить всю партию на день 14; цель игрока остаётся 62.",
        "sphere": "supply"
      },
      {
        "id": "urgent",
        "label": "Срочный проект",
        "description": "2 часа в день; можно обсудить помощника и перенос отчёта.",
        "sphere": "team"
      },
      {
        "id": "reprioritize",
        "label": "Переприоритизация без помощника",
        "description": "Помощник недоступен, срочность менее ценна. При цели 45 эта комбинация может быть отклонена — ресурсы не добавляются автоматически.",
        "sphere": "team"
      }
    ]
  },
  {
    "field": "difficulty",
    "label": "Сложность",
    "help": "Меняет готовность раскрывать интересы и уступать. Всегда 8 ходов; критерии оценки сохраняются.",
    "options": [
      {
        "id": "beginner",
        "label": "Начальная",
        "description": "Ниже порог раскрытия интересов и требований к предложению."
      },
      {
        "id": "normal",
        "label": "Обычная",
        "description": "Базовая политика переговоров."
      },
      {
        "id": "advanced",
        "label": "Повышенная",
        "description": "Больше подготовки для раскрытия интересов и приемлемого предложения."
      }
    ]
  },
  {
    "field": "tone",
    "label": "Тон оппонента",
    "help": "Меняет исходное доверие и напряжение; при скептическом тоне признание факта слабее снимает напряжение.",
    "options": [
      {
        "id": "friendly",
        "label": "Дружелюбный",
        "description": "Выше исходное доверие, ниже напряжение."
      },
      {
        "id": "neutral",
        "label": "Нейтральный",
        "description": "Обычное исходное доверие."
      },
      {
        "id": "skeptical",
        "label": "Скептический",
        "description": "Ниже исходное доверие; отношения восстанавливаются медленнее."
      }
    ]
  },
  {
    "field": "opponentRole",
    "label": "Роль оппонента",
    "help": "Меняет реальные полномочия по цене или назначению помощника.",
    "options": [
      {
        "id": "director",
        "label": "Директор продаж",
        "description": "Более широкие полномочия по согласованию цены.",
        "sphere": "supply"
      },
      {
        "id": "account_manager",
        "label": "Менеджер по работе с клиентом",
        "description": "Ограниченные полномочия по согласованию цены.",
        "sphere": "supply"
      },
      {
        "id": "specialist",
        "label": "Специалист",
        "description": "Предлагает помощника только после выделения ресурса игроком.",
        "sphere": "team"
      },
      {
        "id": "team_lead",
        "label": "Руководитель группы",
        "description": "Может самостоятельно предложить доступного помощника.",
        "sphere": "team"
      }
    ]
  },
  {
    "field": "opponentGoals",
    "label": "Цели оппонента",
    "help": "Меняет предпочтения и границу приемлемости; недостижимая цель блокирует публикацию.",
    "options": [
      {
        "id": "cashflow",
        "label": "Оборотные средства",
        "description": "Предоплата важна для закупки сырья.",
        "sphere": "supply"
      },
      {
        "id": "margin",
        "label": "Доходность сделки",
        "description": "Предоплата менее ценна, граница приемлемости выше. С ролью менеджера целевой результат может быть недостижим.",
        "sphere": "supply"
      },
      {
        "id": "protect_load",
        "label": "Сохранить нагрузку",
        "description": "Сохранить самостоятельность и ранее согласованную работу.",
        "sphere": "team"
      },
      {
        "id": "deliver_scope",
        "label": "Выполнить полный объём",
        "description": "Полный объём более ценен, граница приемлемости выше.",
        "sphere": "team"
      }
    ]
  }
];
const Hash = z.string().regex(/^[a-f0-9]{64}$/);
const Revision = z.int().min(0).max(1_000_000_000);
const RequestId = z.uuid();
export const BindingSchema = z.strictObject({ expectedRevision: Revision, settingsHash: Hash, requestId: RequestId });
export const SaveDraftSchema = BindingSchema.extend({ settings: SettingsSchema });
export const PublishCandidateSchema = BindingSchema.extend({ candidateHash: Hash, approved: z.literal(true) });
export const ValidationIssueSchema = z.strictObject({
  fields: z.array(z.enum(['sphere','topic','difficulty','tone','opponentRole','opponentGoals'])).min(1).max(6),
  message: z.string().min(1).max(500),
});
export const CandidateValidationSchema = z.strictObject({
  status: z.enum(['valid', 'invalid']), revision: Revision, settingsHash: Hash,
  compilerVersion: z.string().min(1).max(64), candidateHash: Hash.nullable(),
  issues: z.array(ValidationIssueSchema).max(12),
  summary: z.string().min(1).max(1000), preview: CatalogReferenceSchema.nullable(),
});
export const DraftSchema = z.strictObject({
  revision: Revision, settingsHash: Hash, settings: SettingsSchema,
  validation: CandidateValidationSchema.nullable(),
});
export const ContextPublicationSchema = z.strictObject({ publication: PublishedCatalogScenarioSchema, revision: Revision, candidateHash: Hash });
export type Draft = z.infer<typeof DraftSchema>;
export type CandidateValidation = z.infer<typeof CandidateValidationSchema>;
export type ContextPublication = z.infer<typeof ContextPublicationSchema>;
