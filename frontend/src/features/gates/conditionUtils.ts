import type { ConditionIn } from './api';

export const emptyCondition = (): ConditionIn => ({
  item_id: '',
  owner_user_id: '',
  due_gate: '',
  text: '',
});

export const conditionComplete = (c: ConditionIn) =>
  !!c.item_id.trim() && !!c.owner_user_id && !!c.due_gate && !!c.text.trim();
