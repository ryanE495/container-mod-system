import os
from datetime import datetime
import json
import pdfkit
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from products import PRODUCT_CATALOG

load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('order_form.html', catalog=PRODUCT_CATALOG)

@app.route('/generate-quote', methods=['POST'])
def generate_quote():
    data = request.json
    
    # Save order to JSON file
    order_id = save_order(data)
    
    # Generate PDF
    generate_pdf(order_id, data)
    
    return jsonify({
        'success': True,
        'order_id': order_id
    })

def save_order(data):
    # Create orders directory if it doesn't exist
    os.makedirs('orders', exist_ok=True)
    
    # Generate unique order ID
    order_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save order data to JSON file
    with open(f'orders/order_{order_id}.json', 'w') as f:
        json.dump(data, f, indent=4)
    
    return order_id

def generate_pdf(order_id, data):
    # Create HTML content for PDF
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .header {{ margin-bottom: 30px; }}
            .order-info {{ margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            .total {{ font-weight: bold; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Purchase Order #{order_id}</h1>
            <p>Date: {datetime.now().strftime('%Y-%m-%d')}</p>
        </div>
        
        <div class="order-info">
            <h3>Customer Information</h3>
            <p>Name: {data['customer']['name']}</p>
            <p>Email: {data['customer']['email']}</p>
            <p>Phone: {data['customer']['phone']}</p>
            <p>Address: {data['customer']['address']}</p>
        </div>

        <h3>Order Details</h3>
        <table>
            <tr>
                <th>Item</th>
                <th>Quantity</th>
                <th>Price</th>
                <th>Total</th>
            </tr>
    """
    
    total = 0
    for item in data['items']:
        unit_price = item['basePrice']
        item_total = unit_price * item['quantity']
        total += item_total
        
        html_content += f"""
            <tr>
                <td>{item['name']}</td>
                <td>{item['quantity']}</td>
                <td>${unit_price:.2f}</td>
                <td>${item_total:.2f}</td>
            </tr>
        """

    html_content += f"""
        </table>
        <div class="total">
            <p>Total Amount: ${total:.2f}</p>
        </div>
        
        <div class="notes">
            <h3>Additional Notes</h3>
            <p>{data.get('notes', '')}</p>
        </div>
    </body>
    </html>
    """

    # Ensure pdfs directory exists
    os.makedirs('pdfs', exist_ok=True)
    
    # Generate PDF
    pdf_path = f'pdfs/order_{order_id}.pdf'
    pdfkit.from_string(html_content, pdf_path)
    
    return pdf_path

@app.route('/download-pdf/<order_id>')
def download_pdf(order_id):
    pdf_path = f'pdfs/order_{order_id}.pdf'
    return send_file(pdf_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)