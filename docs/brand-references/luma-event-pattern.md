# Luma — Event Tech & Networking Reference (Live Browser Verified)

- **Canonical URL**: `https://luma.com` (redirects from `https://lu.ma`)
- **Favicon**: `https://lu.ma/favicon.ico`
- **Local Capture**: [luma-latest.png](file:///c:/Users/04gab/OneDrive%20-%20UPV/Escritorio/JUNCTION/docs/brand-references/captures/luma-latest.png)
- **Core Value Proposition**: Event hosting, discovery, and RSVP management ("Delightful events start here" — from launch parties to community meetups).

## Live Computed Styles (`browser` verification)

- **Typography**: `Inter`, `h1` computed at `52px`
- **Colors**:
  - Primary Ink: `#131517`
  - `--secondary-color`: `#6b7280`
  - `--border-subtle`: `rgba(19, 21, 23, 0.08)`
- **CTA Button**: Background `#131517`, `border-radius: 8px`, `box-shadow: none`

## Real Image Assets (`img.src`)

- `https://images.lumacdn.com/home/hero-phone-mockup.png`
- `https://images.lumacdn.com/home/event-card-preview.png`

## Captured HTML/CSS Pattern Snippet

```html
<article class="luma-event-card">
  <img src="https://images.lumacdn.com/home/event-card-preview.png" alt="Event preview" />
  <div class="luma-event-meta">
    <h3>Founder &amp; VC Deal-Flow Breakfast</h3>
    <p>Thu, Nov 19 · 09:00</p>
  </div>
  <a class="luma-cta" href="/create">RSVP</a>
</article>
```

```css
.luma-event-card {
  background: #ffffff;
  border: 1px solid rgba(19, 21, 23, 0.08);
  border-radius: 8px;
  box-shadow: none;
  color: #131517;
  font-family: 'Inter', sans-serif;
}

.luma-event-meta p {
  color: #6b7280;
  font-variant-numeric: tabular-nums;
}

.luma-cta {
  background: #131517;
  color: #ffffff;
  border-radius: 8px;
  box-shadow: none;
}
```
