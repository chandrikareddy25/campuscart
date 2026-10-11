export function categoryOf(product) {
  if(product.category) return product.category;
  const name = product.name.toLowerCase();
  if (/backpack|bag/.test(name)) return 'Bags';
  if (/book/.test(name) && !/notebook/.test(name)) return 'Books';
  if (/pen|notebook|planner/.test(name)) return 'Stationery';
  return 'Accessories';
}
export function artOf(product) {
  const name = product.name.toLowerCase();
  if (/headphone/.test(name)) return 'headphones';
  if (/hoodie|coat/.test(name)) return 'hoodie';
  if (/mug/.test(name)) return 'mug';
  if (/calculator|hub/.test(name)) return 'tech';
  if (/goggle/.test(name)) return 'goggles';
  if (/tote|sleeve|organizer|backpack|bag/.test(name)) return 'bag';
  if (/bottle/.test(name)) return 'bottle';
  if (/planner/.test(name)) return 'planner';
  if (/pen/.test(name)) return 'pens';
  if (/notebook/.test(name)) return 'notebook';
  return 'book';
}
export const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(value));
