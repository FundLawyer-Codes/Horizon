import math

def generate_svg():
    width = 800
    height = 200
    
    # Sunset/Sunrise Palette - WARMER
    # Sky Gradient: Deep Indigo -> Magenta -> Vibrant Orange -> Sunlight Yellow
    sky_top = "#312e81"      # Indigo 900
    sky_mid_top = "#be185d"  # Pink 700
    sky_mid_bot = "#f97316"  # Orange 500
    sky_bottom = "#fbbf24"   # Amber 400
    
    # Sun
    sun_core = "#fffbeb"     # Amber 50
    sun_outer = "#fbbf24"    # Amber 400
    
    # Mountains (Silhouettes against the light)
    # Distant: Hazy Purple
    mountain_back = "#701a75" 
    # Foreground: Dark Indigo
    mountain_front = "#4c1d95" 
    
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
    <defs>
        <linearGradient id="skyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:{sky_top};stop-opacity:1" />
            <stop offset="40%" style="stop-color:{sky_mid_top};stop-opacity:1" />
            <stop offset="70%" style="stop-color:{sky_mid_bot};stop-opacity:1" />
            <stop offset="100%" style="stop-color:{sky_bottom};stop-opacity:1" />
        </linearGradient>
        
        <filter id="sunGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="15" result="blur"/>
            <feComposite in="SourceGraphic" in2="blur" operator="over"/>
        </filter>
        
        <linearGradient id="sunInnerGradient" x1="0%" y1="0%" x2="0%" y2="100%">
             <stop offset="0%" style="stop-color:#ffffff;stop-opacity:1" />
             <stop offset="100%" style="stop-color:#fef3c7;stop-opacity:1" />
        </linearGradient>

        <linearGradient id="textGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:#ffffff;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#fed7aa;stop-opacity:1" />
        </linearGradient>
    </defs>

    <!-- Sky Background -->
    <rect width="{width}" height="{height}" fill="url(#skyGradient)" />
    
    <!-- Morning Sun (Rising) -->
    <circle cx="400" cy="120" r="50" fill="#fcd34d" filter="url(#sunGlow)" opacity="0.6" />
    <circle cx="400" cy="120" r="30" fill="url(#sunInnerGradient)" opacity="0.95" />
    
    <!-- Horizon Grid Lines (Digital Landscape feeling) -->
    <g stroke="white" stroke-width="0.5" opacity="0.15">
        <!-- Horizontal lines getting closer together towards horizon -->
        <line x1="0" y1="120" x2="{width}" y2="120" />
        <line x1="0" y1="140" x2="{width}" y2="140" />
        <line x1="0" y1="155" x2="{width}" y2="155" />
        <line x1="0" y1="165" x2="{width}" y2="165" />
        <line x1="0" y1="172" x2="{width}" y2="172" />
    </g>

    <!-- Back Mountains (Distant) -->
    <path d="M0,200 L0,150 C150,160 250,130 400,150 C550,170 650,150 800,160 L800,200 Z" fill="{mountain_back}" opacity="0.6" />
    
    <!-- Front Mountains (Foreground) -->
    <path d="M-10,200 L-10,180 C100,195 300,165 400,175 C500,185 700,165 810,185 L810,200 Z" fill="{mountain_front}" opacity="0.9" />

    <!-- Text -->
    <text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" font-family="'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-weight="900" font-size="70" fill="url(#textGradient)" letter-spacing="12" style="text-shadow: 0px 4px 10px rgba(0,0,0,0.4);">
        HORIZON
    </text>
    
    <text x="50%" y="85%" dominant-baseline="middle" text-anchor="middle" font-family="'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="13" fill="#fbbf24" letter-spacing="4" opacity="0.95" font-weight="bold">
        INTELLIGENCE AGGREGATOR
    </text>
</svg>'''
    
    return "".join(svg_content.split('\n'))

if __name__ == "__main__":
    with open('docs/assets/horizon-header.svg', 'w') as f:
        f.write(generate_svg())
    print("SVG generated successfully at docs/assets/horizon-header.svg")
