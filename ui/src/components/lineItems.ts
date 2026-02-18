export type LineItem = {
  label: string;
  min: number;
  max: number;
};

export function totalFromLineItems(items: LineItem[]): { min: number; max: number } {
  return items.reduce(
    (acc, item) => ({ min: acc.min + item.min, max: acc.max + item.max }),
    { min: 0, max: 0 }
  );
}
