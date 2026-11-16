import { describe, expect, it } from 'vitest';
import { categoryLabel } from '../catalog-shared';

describe('categoryLabel', () => {
  it('renders a dotted path as a readable trail', () => {
    expect(categoryLabel('home.decor')).toBe('Home · Decor');
    expect(categoryLabel('seasonal.christmas')).toBe('Seasonal · Christmas');
    expect(categoryLabel('stationery.giftwrap')).toBe('Stationery · Giftwrap');
  });

  it('handles a single segment and underscores', () => {
    expect(categoryLabel('jewellery')).toBe('Jewellery');
    expect(categoryLabel('party.celebration_extras')).toBe('Party · Celebration Extras');
  });

  it('leaves the uncategorised bucket readable', () => {
    expect(categoryLabel('uncategorised')).toBe('Uncategorised');
  });
});
