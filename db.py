import psycopg2



def get_connection():
    return psycopg2.connect(
        host="db.vhrkitmevkgtoudilbmo.supabase.co",
        database="postgres",
        user="postgres",
        password="94BmzfxfN9hxxoTP",
        port="5432"
    )


